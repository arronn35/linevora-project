# Linevora

MVP skeleton of the inquiry-to-quote flow for industrial requests.
Architecture: `docs/architecture/README.md`; data model: `docs/architecture/data-model.md`.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running

```sh
source .venv/bin/activate
python -m uvicorn linevora.main:app --reload
```

API: `http://127.0.0.1:8000/v1/health`

## Tests

```sh
source .venv/bin/activate
pytest -q
```

## Eval Gate

```sh
source .venv/bin/activate
python eval/run_eval.py --cases eval/cases --extractor perfect --min-score 0.8
```

If the threshold is missed, the exit code is 1. The `perfect`/`empty`
extractors exist for the harness to test itself; `scripted` runs the real
extractor code path with scripted model responses (a plumbing test; real
accuracy measurement is done with the same runner once a managed model
adapter is added).

## Panel

The UI lives in `site/` (React + Vite) and is served by FastAPI from a
single port: `http://127.0.0.1:8000/` is the showcase and
`http://127.0.0.1:8000/panel` is the operations panel. The panel covers
sign-in, inquiries (version upload, processing, suggestions / gaps /
alternatives / diff / quote preview), the catalog, versioned prices and
terms, live observability and the audit log.

Observability (admin only): a live status strip at the top (health, job
queue, model); in the Observability tab, metric cards, the dead-letter
list and the live audit stream; data refreshes every 4 seconds and pauses
while the tab is hidden.

On first setup, build the frontend once (Node required):

```sh
cd site && npm install && npm run build && cd ..
python -m uvicorn linevora.main:app --reload
```

For hot reload during development, use `cd site && npm run dev`
(:5173; `/v1` requests are proxied to :8000). When `site/dist` is absent,
the panel falls back, for backward compatibility, to the plain version
bundled in the package (`src/linevora/web`).
Sign-in: `admin` / `admin123` (roles: admin, specialist, viewer).

## API Surfaces

- `GET /v1/health` — health (public)
- `POST /v1/auth/token` — token issuing
- `GET /v1/me` — who am I
- `GET /v1/audit` — audit reading (admin only)
- `POST /v1/inquiries` — open an inquiry (admin/specialist)
- `POST /v1/inquiries/{id}/versions` — upload a version (admin/specialist)
- `GET /v1/inquiries/{id}/versions` — list versions
- `POST /v1/inquiries/{id}/versions/{v}/process` — requirement extraction + matching job (admin/specialist)
- `GET /v1/jobs/{job}` — job status
- `GET /v1/inquiries/{id}/versions/{v}/suggestions` — requirements and scored suggestions
- `GET /v1/inquiries/{id}/versions/{v}/gaps` — missing-information list
- `GET /v1/inquiries/{id}/versions/{a}/diff/{b}` — version diff report
- `GET /v1/inquiries/{id}/versions/{v}/alternatives` — criterion-compared alternatives
- `GET/POST /v1/products`, `GET/POST /v1/prices`, `POST /v1/prices/{id}/activate` — catalog and versioned prices
- `GET/POST /v1/terms`, `POST /v1/terms/{id}/activate` — versioned terms
- `POST /v1/inquiries/{id}/versions/{v}/quotes` — quote draft
- `GET /v1/quotes/{id}`, `PUT /v1/quotes/{id}/lines` — reading a quote and editing a draft
- `POST /v1/quotes/{id}/submit|return|approve`, `GET /v1/quotes/{id}/export` — approval flow
- `GET /v1/metrics`, `POST /v1/admin/snapshot` — metrics and snapshots (admin only)

Operations (backup, security, pilot acceptance): `docs/operations.md`.

## Configuration (environment variables)

- `LINEVORA_SECRET_KEY`: token signing key (required in production; use a strong value).
- `LINEVORA_TOKEN_TTL`: token lifetime in seconds (default 3600).
- `LINEVORA_USERS`: users in `user:password:role,...` form.
  Default (development only): `admin:admin123:admin,specialist:specialist123:specialist,viewer:viewer123:viewer`.
- `LINEVORA_ENV`: `dev` or `prod` (default `dev`).
- `LINEVORA_BLOB_DIR`: file store directory (default `var/blobs`).
- `LINEVORA_SNAPSHOT_PATH`: snapshot file (when unset, snapshots are disabled).
- `LINEVORA_DB_PATH`: SQLite persistence file (e.g. `var/linevora.db`). When set, all records survive restarts; otherwise state is in-memory.
- `LINEVORA_MODEL_URL` / `LINEVORA_MODEL_API_KEY` / `LINEVORA_MODEL_NAME` / `LINEVORA_MODEL_TIMEOUT`: managed model service (OpenAI-compatible chat endpoint). When `URL` is empty, the fake client is used.
- `LINEVORA_MATCHER`: `lexical` (default), `vector`, or `hybrid`.
- `LINEVORA_RATE_LIMIT_PER_MINUTE`: rate limit for the token endpoint (default 60).
- A `pbkdf2_sha256$...` hash is also accepted in the password field: `python -c "from linevora.auth.passwords import hash_password; print(hash_password('password'))"`.
- Approved-quote PDF: `GET /v1/quotes/{id}/export.pdf`. Token revocation: `POST /v1/auth/revoke`.
