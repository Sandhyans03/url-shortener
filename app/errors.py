"""Domain errors and the handlers that turn every error into one JSON shape.

Every error response looks like::

    {"error": {"code": "link_not_found", "message": "...", "details": [...]}}

`code` is stable and machine-readable; `message` is for humans.
`details` is only present for request validation errors.
"""

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LinkNotFound(AppError):
    status_code = 404
    code = "link_not_found"

    def __init__(self, code: str):
        super().__init__(f"No short link exists for code '{code}'.")


class LinkExpired(AppError):
    status_code = 410
    code = "link_expired"

    def __init__(self, code: str, expired_at: datetime):
        super().__init__(
            f"The short link '{code}' expired on "
            f"{expired_at:%Y-%m-%d %H:%M:%S} UTC and is no longer available."
        )


class AliasTaken(AppError):
    status_code = 409
    code = "alias_taken"

    def __init__(self, alias: str):
        super().__init__(
            f"The alias '{alias}' is already in use. "
            "Choose a different alias, or omit it to get a generated code."
        )


class InvalidExpiry(AppError):
    status_code = 422
    code = "invalid_expiry"

    def __init__(self):
        super().__init__("expires_at must be a time in the future.")


class CodeGenerationFailed(AppError):
    status_code = 503
    code = "code_generation_failed"

    def __init__(self):
        super().__init__("Could not generate a unique short code. Please retry.")


def error_payload(code: str, message: str, details: list[dict] | None = None) -> dict:
    body: dict = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


_HTTP_ERROR_CODES = {
    404: "not_found",
    405: "method_not_allowed",
}


def _field_name(loc: tuple) -> str:
    # loc looks like ("body", "alias"); drop the leading "body"/"query"/...
    parts = [str(p) for p in loc[1:]]
    return ".".join(parts) or "body"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": _field_name(err["loc"]),
                "message": err["msg"].removeprefix("Value error, "),
            }
            for err in exc.errors()
        ]
        summary = "; ".join(f"{d['field']}: {d['message']}" for d in details)
        return JSONResponse(
            status_code=422,
            content=error_payload("validation_error", f"Invalid request. {summary}", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )
