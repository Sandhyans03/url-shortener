# URL Shortener API

A small URL-shortening service built with **FastAPI** and **SQLAlchemy**, storing data in **SQLite** (Postgres works too, see [Configuration](#configuration)).

- Create short links with an optional custom alias and optional expiry
- Redirect `GET /{code}` to the original URL (`404` unknown, `410` expired)
- Per-link click counting with `GET /links/{code}/stats`
- URL and alias validation, duplicate aliases rejected with `409`
- One consistent JSON error format
- 46 automated tests (pytest)

## Setup

Requires Python 3.10+.

```bash
git clone <your-repo-url> url-shortener
cd url-shortener

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The API is now at <http://localhost:8000>. Interactive docs (Swagger UI) are at <http://localhost:8000/docs>.
The SQLite database file `shortener.db` is created automatically in the working directory on first start.

## Run the tests

```bash
pytest
```

Tests use a temporary SQLite database per test and a fake clock, so expiry and "last clicked" are tested exactly, with no sleeping.

## Endpoints

| Method | Path                    | Description                                  | Success | Errors             |
|--------|-------------------------|----------------------------------------------|---------|--------------------|
| POST   | `/links`                | Create a short link                          | `201`   | `409`, `422`       |
| GET    | `/{code}`               | Redirect to the original URL (counts a click)| `307`   | `404`, `410`       |
| GET    | `/links/{code}/stats`   | Total clicks and last clicked time           | `200`   | `404`              |
| GET    | `/health`               | Liveness check                               | `200`   |                    |

### `POST /links`

Request body:

| Field        | Required | Description |
|--------------|----------|-------------|
| `url`        | yes      | The `http`/`https` URL to shorten (max 2048 chars, must have a valid host). |
| `alias`      | no       | Custom code: 3-32 chars, letters, digits, `-` or `_`. Case-sensitive. A random 7-character code is generated if omitted. `links`, `docs`, `redoc` and `health` are reserved. |
| `expires_at` | no       | ISO 8601 timestamp, must be in the future. Without a UTC offset it is treated as UTC. |

### `GET /links/{code}/stats`

Returns `total_clicks`, `last_clicked_at` (`null` until the first click), plus `original_url`, `created_at`, `expires_at` and `is_expired`. Stats stay available after a link expires.

## Example requests

```bash
# Create a link with a generated code
curl -X POST http://localhost:8000/links \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/some/very/long/path?utm_source=newsletter"}'

# Create a link with a custom alias and an expiry
curl -X POST http://localhost:8000/links \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/spring", "alias": "spring-sale", "expires_at": "2026-12-31T23:59:59Z"}'
```

```json
{
  "code": "spring-sale",
  "short_url": "http://localhost:8000/spring-sale",
  "original_url": "https://example.com/spring",
  "created_at": "2026-10-25T10:30:24.921042Z",
  "expires_at": "2026-12-31T23:59:59Z"
}
```

```bash
# Follow the short link (-i shows the 307 and its Location header)
curl -i http://localhost:8000/spring-sale

# Click statistics
curl http://localhost:8000/links/spring-sale/stats
```

```json
{
  "code": "spring-sale",
  "original_url": "https://example.com/spring",
  "created_at": "2026-10-25T10:30:24.921042Z",
  "expires_at": "2026-12-31T23:59:59Z",
  "is_expired": false,
  "total_clicks": 1,
  "last_clicked_at": "2026-10-25T10:31:02.114873Z"
}
```

## Error format

Every error, including unknown routes and validation failures, has the same shape:

```json
{ "error": { "code": "alias_taken", "message": "The alias 'spring-sale' is already in use. Choose a different alias, or omit it to get a generated code." } }
```

| Status | `code`               | When |
|--------|----------------------|------|
| 404    | `link_not_found`     | No link exists for that code |
| 410    | `link_expired`       | The link's expiry time has passed (message says when) |
| 409    | `alias_taken`        | The requested alias already exists |
| 422    | `validation_error`   | Bad URL or alias; `details` lists each problem by field |
| 422    | `invalid_expiry`     | `expires_at` is not in the future |
| 503    | `code_generation_failed` | Could not find a free random code after several tries (practically never) |

Validation example:

```bash
curl -X POST http://localhost:8000/links -H 'Content-Type: application/json' \
  -d '{"url": "ftp://example.com", "alias": "x"}'
```

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request. url: URL must start with http:// or https://.; alias: Alias must be 3-32 characters and contain only letters, digits, '-' or '_'.",
    "details": [
      { "field": "url", "message": "URL must start with http:// or https://." },
      { "field": "alias", "message": "Alias must be 3-32 characters and contain only letters, digits, '-' or '_'." }
    ]
  }
}
```

## Configuration

Environment variables:

| Variable       | Default                    | Purpose |
|----------------|----------------------------|---------|
| `DATABASE_URL` | `sqlite:///./shortener.db` | Any SQLAlchemy URL. For Postgres, `pip install "psycopg[binary]"` and use e.g. `postgresql+psycopg://user:pass@localhost/shortener`. |
| `BASE_URL`     | the request's own origin   | Public origin used to build `short_url`, e.g. `https://sho.rt`. Set this when running behind a proxy. |

## Design notes

- **Layering.** `api.py` (HTTP) → `services.py` (business rules) → `models.py`/`db.py` (storage). Routes contain no logic beyond shaping requests and responses; the service has no knowledge of HTTP. Domain errors live in `errors.py` and are converted to responses in one place.
- **Duplicate aliases are race-free.** Uniqueness is enforced by a database `UNIQUE` constraint rather than a check-then-insert, so two simultaneous requests for the same alias cannot both succeed. The same constraint makes random-code collisions safe: the insert is simply retried with a new code.
- **Click counting is atomic.** Clicks are recorded with a single SQL `UPDATE ... SET click_count = click_count + 1`, so concurrent visits are never lost. Only successful redirects count; 404/410 visits and stats lookups do not.
- **Expiry.** A link is expired when `now >= expires_at`. Time comes from an injected clock, which is how the tests control it. An expired code stays reserved, so its alias can't be silently reassigned to a different destination.
- **Redirect status.** `307` (temporary) is used so browsers and proxies do not cache the redirect and skip the click counter. The stored URL is returned exactly as submitted.
- **Timestamps** are stored as UTC and always returned with a `Z` suffix.

## Project layout

```
app/
  main.py       app factory, lifespan (creates tables)
  api.py        routes
  services.py   create / resolve / stats rules
  schemas.py    request & response models, URL and alias validation
  models.py     SQLAlchemy model (Link)
  errors.py     domain errors + unified error handlers
  db.py         engine and session factory
  deps.py       FastAPI dependencies
  config.py     environment-based settings
  clock.py      injectable time source
tests/
  conftest.py          fixtures, fake clock
  test_create_link.py  creation, aliases, URL/expiry validation
  test_redirect.py     redirects, 404, 410, expiry boundary
  test_stats.py        click counting and stats
```

## Possible next steps

Not built, to keep the scope focused: authentication / per-user links, rate limiting, deleting or updating links, Alembic migrations (tables are created with `create_all` on startup), and a click-event log with referrer/user-agent for richer analytics.
