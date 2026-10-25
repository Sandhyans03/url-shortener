"""Request/response schemas and input validation rules."""

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

MAX_URL_LENGTH = 2048
ALIAS_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,32}")
# Aliases that would collide with real routes (/links, /docs, ...).
RESERVED_ALIASES = frozenset({"links", "docs", "redoc", "health"})


def _is_plausible_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) >= 2 and all(labels)


def validate_http_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("URL must not be empty.")
    if len(value) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters long.")
    if any(ch.isspace() for ch in value):
        raise ValueError("URL must not contain whitespace.")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        _ = parts.port  # raises ValueError for a malformed or out-of-range port
    except ValueError:
        raise ValueError("URL is malformed.") from None
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://.")
    if not host or not _is_plausible_host(host):
        raise ValueError("URL must include a valid host, e.g. https://example.com/page.")
    return value


class LinkCreate(BaseModel):
    url: str = Field(description="The long URL to shorten (http or https).")
    alias: str | None = Field(
        default=None,
        description=(
            "Optional custom short code: 3-32 characters, letters, digits, '-' or '_'. "
            "Case-sensitive. A random code is generated when omitted."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "Optional expiry as an ISO 8601 timestamp; must be in the future. "
            "Timestamps without a UTC offset are treated as UTC."
        ),
    )

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_http_url(value)

    @field_validator("alias")
    @classmethod
    def _check_alias(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ALIAS_PATTERN.fullmatch(value):
            raise ValueError(
                "Alias must be 3-32 characters and contain only letters, digits, '-' or '_'."
            )
        if value.lower() in RESERVED_ALIASES:
            raise ValueError(f"'{value}' is reserved and cannot be used as an alias.")
        return value

    @field_validator("expires_at")
    @classmethod
    def _to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class LinkCreated(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None


class LinkStats(BaseModel):
    code: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None
    is_expired: bool
    total_clicks: int
    last_clicked_at: datetime | None


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
