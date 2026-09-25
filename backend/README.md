# Case Law — Backend

FastAPI application that serves the search, detail and indicator endpoints.

## Requirements

- [uv](https://docs.astral.sh/uv/) — manages Python and the dependencies
- Docker — only for the PostgreSQL container

Linux and macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Then close every open terminal and open a new one.** A shell reads `PATH` when
it starts, so one that was already open when `uv` was installed will keep saying
the command does not exist. In VS Code, closing the terminal panel is not enough:
the editor passes its own environment to each new terminal, so quit VS Code and
reopen it.

You do **not** need to install Python by hand. `uv` reads `.python-version`
and downloads the right version on its own.

## Setup

`uv run` works from a directory that has a `pyproject.toml`. In this repository
that means `backend/` — from the repository root it will not find the project.

```bash
cd backend
uv sync
```

Then create your `.env` from the template:

```bash
cp .env.example .env          # Linux, macOS
```

```powershell
Copy-Item .env.example .env   # Windows
```

## Data to develop against

`docker compose up -d` at the repository root gives you an **empty** PostgreSQL.
The API starts fine against it and answers `503 NOT_PUBLISHED` on the search
endpoints, which is the same answer a server gives before its first publication.
Enough to work on the interface's loading and error states, not enough to see a
result list.

The collection is loaded by the pipeline, which runs on one machine and is then
published to the servers. You do not need to run it to work on the API or the
interface. Ask whoever runs it for a sample dump instead: a few thousand
decisions is a 5 MB file and behaves like the real thing for search, ordering
and paging.

Producing one, from the repository root on the machine that has the data:

```bash
docker compose exec -T postgres psql -U postgres -d caselaw \
  -c "DROP SCHEMA IF EXISTS amostra CASCADE" \
  -c "CREATE SCHEMA amostra" \
  -c "CREATE TABLE amostra.tribunal AS SELECT * FROM core.tribunal" \
  -c "CREATE TABLE amostra.fonte AS SELECT * FROM core.fonte" \
  -c "CREATE TABLE amostra.decisao AS SELECT * FROM core.decisao ORDER BY random() LIMIT 2000"

docker compose exec -T postgres pg_dump -U postgres -d caselaw \
  --schema amostra --no-owner --format custom --compress 9 > amostra.dump
```

Loading it, on the machine that received the file. Copy it into the container
first and restore from there: PowerShell has no `<` redirection, so feeding the
file through standard input works on some shells and not others, while this runs
the same everywhere.

```bash
docker compose cp amostra.dump postgres:/tmp/amostra.dump

docker compose exec -T postgres pg_restore -U postgres -d caselaw \
  --no-owner --no-privileges /tmp/amostra.dump

docker compose exec -T postgres psql -U postgres -d caselaw \
  -c "DROP SCHEMA IF EXISTS core CASCADE" \
  -c "ALTER SCHEMA amostra RENAME TO core"

docker compose exec -T postgres rm /tmp/amostra.dump
```

`docker compose` has to run from the repository root, where `docker-compose.yml`
is. The dump itself can be anywhere — pass its full path to `cp`.

The search index is not carried by the sample. Create it after loading, or the
first search will scan the whole table:

```bash
docker compose exec -T postgres psql -U postgres -d caselaw \
  -c "CREATE INDEX ON core.decisao USING gin (ementa_busca)"
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

## Tests that need PostgreSQL

Most tests run anywhere: the database connection is injected, so they never open
a socket. The ones that check search behaviour do need a real PostgreSQL, because
what they verify — accent folding, the query syntax, the text index — lives in the
database, not in Python.

They are skipped unless `TEST_DATABASE_URL` points at a database:

Create the database once, from the repository root:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE caselaw_test"
```

Then point the variable at it and run the tests, back in `backend/`:

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/caselaw_test uv run pytest
```

PowerShell has no inline form for this — writing the assignment before the
command is a syntax error there. Set it first, and it lasts for that terminal:

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/caselaw_test"
uv run pytest
```

Watch the count. Without the variable the database tests are **skipped**, not
failed, so a run that says `passed` may have exercised half of what you think.

Use a database of its own. The fixture drops and recreates the `core` schema, and
pointing it at the development database would take the loaded data with it.

CI sets the variable itself, so every pull request runs them.
