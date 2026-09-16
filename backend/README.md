# Case Law — Backend

FastAPI application that serves the search, detail and indicator endpoints.

## Requirements

- [uv](https://docs.astral.sh/uv/) — manages Python and the dependencies
- Docker — only for the PostgreSQL container

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

You do **not** need to install Python by hand. `uv` reads `.python-version`
and downloads the right version on its own.

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

## Running

```bash
uv run uvicorn app.main:app --reload
```

| Address | What it is |
|---|---|
| http://localhost:8000/health | health check |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/openapi.json | the OpenAPI spec |

The port is **not** set in the code — `uvicorn` defaults to 8000. Pass
`--port 8001` to change it.

## Quality checks

The same four commands the CI runs. Run them before opening a pull request:

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy app tests        # type checking
uv run pytest                # tests
```

The scope, scenarios and DevOps handoff for unit tests are documented in
[the repository testing process](../TESTING.md). Run only the unit tests with
`uv run pytest -m unit -v`.

To fix formatting instead of only reporting it:

```bash
uv run ruff format .
```

## Adding a dependency

```bash
uv add <package>             # runtime
uv add --dev <package>       # development only
```

Both update `pyproject.toml` and `uv.lock`. **Commit the lock file** — it is
what keeps every machine on the same versions.

## Structure

```
backend/
├── app/
│   ├── config.py        settings read from environment variables
│   ├── main.py          creates the app and registers the routers
│   └── api/             one module per group of endpoints
├── tests/
└── pyproject.toml       dependencies and tool configuration
```

## Configuration

Every value that differs between a laptop and a server lives in `app/config.py`
and is read from the environment. Never hardcode a URL, port or password.

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/caselaw` | where the data lives |
| `ENVIRONMENT` | `development` | reported by `/health`, so you know which environment answered |
| `CORS_ORIGINS` | `http://localhost:5173` | which origins the browser may call the API from |

`.env.example` is versioned as a template. The real `.env` is ignored by git.

### CORS_ORIGINS

The browser blocks a page on one origin from calling an API on another unless the
API says otherwise. The frontend runs on port 5173 and the API on 8000 — different
origins — so the frontend address has to be listed here.

Accepts several, separated by commas:

```
CORS_ORIGINS=http://localhost:5173,https://caselaw.example.com
```

Never use `*`. It would let any page on the internet call the API on behalf of
whoever is logged in.
