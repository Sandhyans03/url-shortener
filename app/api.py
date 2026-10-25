"""HTTP routes. Thin layer: parse request, call the service, shape the response."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.deps import get_link_service
from app.schemas import ErrorResponse, LinkCreate, LinkCreated, LinkStats
from app.services import LinkService

router = APIRouter()


@router.post(
    "/links",
    response_model=LinkCreated,
    status_code=201,
    tags=["links"],
    summary="Create a short link",
    responses={
        409: {"model": ErrorResponse, "description": "Alias is already in use."},
        422: {"model": ErrorResponse, "description": "Invalid URL, alias or expiry."},
    },
)
def create_link(
    payload: LinkCreate,
    request: Request,
    service: LinkService = Depends(get_link_service),
) -> LinkCreated:
    link = service.create(payload.url, payload.alias, payload.expires_at)
    base_url = request.app.state.settings.base_url or str(request.base_url)
    return LinkCreated(
        code=link.code,
        short_url=f"{base_url.rstrip('/')}/{link.code}",
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.get(
    "/links/{code}/stats",
    response_model=LinkStats,
    tags=["links"],
    summary="Click statistics for a link",
    responses={404: {"model": ErrorResponse, "description": "Unknown code."}},
)
def link_stats(code: str, service: LinkService = Depends(get_link_service)) -> LinkStats:
    link = service.get_stats(code)
    return LinkStats(
        code=link.code,
        original_url=link.original_url,
        created_at=link.created_at,
        expires_at=link.expires_at,
        is_expired=service.is_expired(link),
        total_clicks=link.click_count,
        last_clicked_at=link.last_clicked_at,
    )


@router.get("/health", tags=["meta"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Registered last so it never shadows the fixed routes above.
@router.get(
    "/{code}",
    status_code=307,
    tags=["redirect"],
    summary="Redirect to the original URL",
    responses={
        307: {"description": "Redirect to the original URL (counts as a click)."},
        404: {"model": ErrorResponse, "description": "Unknown code."},
        410: {"model": ErrorResponse, "description": "The link has expired."},
    },
)
def follow_link(code: str, service: LinkService = Depends(get_link_service)):
    destination = service.register_click(code)
    return RedirectResponse(destination, status_code=307)
