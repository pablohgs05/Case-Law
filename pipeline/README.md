# Case Law — Pipeline

Extraction and transformation of judicial decision data. Runs on a developer
machine, not on a server: the data is historical and loaded in batches.

```
  court APIs  ──dlt──>  raw schema  ──SQLMesh──>  treated  ──>  core
```

Two tools for two jobs. **dlt** brings data in without changing it, so a reload
never needs to hit the API again. **SQLMesh** turns the raw data into the tables
the API reads.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- A PostgreSQL to load into — `docker compose up -d` at the repository root

## Setup

```bash
cd pipeline
uv sync
cp .env.example .env
```

## Running the extraction

```bash
uv run python -m sources.tjdft
```

Loads acordaos from the TJDFT JurisDF API into `raw.acordao_tjdft`. With no date
window it walks the whole collection: 1,749,377 documents, 40 per request.

```bash
TJDFT_START_DATE=2026-01-01 TJDFT_END_DATE=2026-01-31 uv run python -m sources.tjdft
```

Restricting the window is the normal way to work. January 2026 alone is 5,417
documents, which is enough to develop against and takes about a minute.

`TJDFT_SUBJECT` narrows further by free text: the same month restricted to
`dano moral` is 533 documents.

### Not hammering the source

One request every half second, measured from the end of the previous one. The
whole collection is 43,734 requests, so the pace decides whether the run takes
six hours or gets the address blocked. `TJDFT_REQUEST_INTERVAL` changes it.

Network failures are retried five times with growing delay, and a `Retry-After`
header is obeyed when the portal sends one. A page that fails every attempt
stops the run rather than leaving a silent hole in the collection.

dlt also creates `raw._dlt_loads` on its own, recording every run with its id,
status and timestamp. That is what `core.carga` reads.

### What the connector does

The API serves five collections from one endpoint, and the default response
mixes acordaos with monocratic decisions, sumulas and newsletters. The connector
asks for `base: acordaos` only, which is the 1,749,377 figure above.

Records are written with `merge` on `identificador`, so running the same window
twice updates rather than duplicates. This matters because `core.decisao`
audits that the pair source plus identifier is unique.

Documents under seal arrive with their full text — the API reports the flag but
does not redact the content. They are kept in the raw layer, because `core.carga`
counts them to report how many were discarded, and dropped on the way into
`core.decisao`.

Two pieces of the response are left out. `marcadores` holds the highlight
positions for the search screen, not anything about the decision. And inside
`jurisprudenciaEmFoco`, the `conteudo` buffer is dropped while its description
and link are kept: dlt writes a buffer as one row per byte, which turned 120
decisions into 1.9 million rows and 328 MB. The whole collection would be
measured in terabytes.

Field names are preserved exactly as the API returns them, camel case included,
which is why the SQL models quote `"dataJulgamento"`. The raw layer mirrors the
source; renaming belongs to the transformation.

### Doctrine, from the BDJur

```bash
uv run python -m sources.doutrina
```

Harvests the STJ's digital library by OAI-PMH into `raw.doutrina_bdjur`: author,
title, where it came out, and the link back. Never the text of the work — open
access is permission to read, not to redistribute.

Only `col_2011_8`, Artigos de Acesso Aberto. The library keeps Acesso Restrito
in a separate collection, `col_2011_9`, and that separation is what settles the
scope: the classification is the STJ's, not ours. Where a record carries
`dc:rights` the field decides, and it is an allow list — one work filed in the
open collection declares `Restricted access`, and it does not enter `core`.

Records are written with `merge` on repository plus OAI identifier, and the
cursor is the record's own datestamp, which is what the protocol's `from`
compares. A second run asks the library only for what changed since the first.

```bash
uv run python -m sources.doutrina --de ~/paginas-bdjur
```

**The endpoint refuses automated access.** It answered on 05/10/2026 and has
answered HTTP 403 since 24/10/2026, by a measure of the STJ's own security
coordination; harvesting access has to be asked for at the address the protocol
publishes, `bdjur@stj.jus.br`. Until it is granted, `--de` reads pages saved by
hand from a browser — the same records, rendered rather than served. Both paths
parse the same `oai_dc` block with the same code, and a test asserts they agree
field by field.

## Checking the links

Each decision carries a link back to the court. Whether that link still reaches
a document is checked here, at load time, and written down — never while
answering a search, which would make the search as slow and as available as the
court's own site.

```bash
uv run python verify_links.py
```

It takes the records nobody has checked yet, newest first, and asks the source
about each one. `VERIFY_MAX` bounds a run (default 1000) and `VERIFY_INTERVAL`
paces it (default 0.5s, the same courtesy the connector uses). Runs are
incremental and resumable: interrupting one keeps everything it had already
written, and the next run picks up where it stopped.

### Why it asks the API and not the page

`detalhes/{identificador}` cannot answer the question. It is a single-page
application: a real identifier and an invented one both come back 200, both
62.758 bytes, because the document arrives later over the API. Checking the page
would mark every link valid, including the broken ones.

So the check queries the same API the connector loads from, by the identifier
the link is built from, and asks whether the document is still there.

### Three states, not two

| `link_valido` | Means |
|---|---|
| `TRUE` | the source still holds the document |
| `FALSE` | the source no longer answers for this identifier |
| `NULL` | nobody has checked it yet |

`NULL` is not `FALSE`. A court portal that is down produces unchecked records,
never broken ones — the run stops after ten failures in a row rather than asking
once per remaining record, and nothing is written. `core.carga` reports
`links_nao_verificados` beside `links_invalidos` for the same reason: zero
invalid means little when nobody looked.

## Running the transformation

```bash
cd transformations
uv run sqlmesh info      # checks the connection and lists the models
uv run sqlmesh plan      # shows what changed before touching anything
```

`plan` is the important one: it reports which models changed and what would be
rebuilt, and waits for confirmation. Add `--auto-apply` to skip the prompt.

## Configuration

Everything comes from the environment. Nothing is hardcoded.

| Variable | Used by | Default |
|---|---|---|
| `POSTGRES_HOST` `POSTGRES_PORT` | SQLMesh | `localhost` `5432` |
| `POSTGRES_DB` `POSTGRES_USER` `POSTGRES_PASSWORD` | SQLMesh | `caselaw` `postgres` `postgres` |
| `DESTINATION__POSTGRES__CREDENTIALS` | dlt | full connection URL |
| `TJDFT_START_DATE` `TJDFT_END_DATE` | TJDFT connector | none — the whole collection |
| `TJDFT_SUBJECT` | TJDFT connector | none — every subject |
| `TJDFT_MAX_PAGES` | TJDFT connector | none — until the source runs out |
| `TJDFT_REQUEST_INTERVAL` | TJDFT connector | `0.5` seconds between requests |
| `BDJUR_PAGINAS` | BDJur connector | none — reads the endpoint, same as `--de` |
| `VERIFY_MAX` | link check | `1000` records per run |
| `VERIFY_INTERVAL` | link check | `0.5` seconds between requests |

dlt uses its own variable name because that is the convention it reads by
default. Keeping it avoids a translation layer that would only be one more thing
to get wrong.

## Structure

```
pipeline/
├── sources/             connectors: what reads each court API
└── transformations/     SQLMesh project
    ├── config.yaml      connection and defaults
    ├── seeds/           what each court is: URL patterns, coverage, status
    └── models/          SQL models
```

## Publishing to the servers

The pipeline runs on a development machine and the servers only host. This is the
step that carries the treated layer across.

```bash
uv run python -m publish dev producao
```

Targets are named, and each one needs three variables — see `.env.example`.

### What travels
Only `core`. The raw layer stays where it was collected: it holds the original
documents, including the ones under seal, and nothing outside this machine needs
them.

`core` is five SQLMesh views over physical tables, so a plain dump would carry
definitions and no rows. The script materialises them into real tables first,
rebuilds the eight indexes, and sends that.

### How the swap avoids a half-loaded state
The restore lands in a schema nobody reads. Only then, in a single transaction,
the old schema is dropped and the new one renamed into its place. Two instant
statements, so a search either sees the previous dataset or the new one — never
a mixture, and never an error.

### What the target gets prepared with
The `unaccent` extension and the `portugues_sem_acento` configuration are created
if missing. Without them the search raises on the server rather than returning
results.

### A case sealed after it was published

Courts seal cases after the fact, and a decision already on the servers can stop
being public. Nothing deletes it there directly.

It does not need to. The core layer is rebuilt from the raw layer on every run,
and the filter drops sealed records on the way through; publication then replaces
the published schema wholesale rather than adding to it. The record is simply
absent from the next one.

Two things have to stay true for that to hold, and both are pinned by tests in
`backend/tests/test_seal_filter.py`:

- the transformation drops anything flagged as sealed, every time it runs
- publication replaces the schema instead of merging into it

Changing publication to an incremental strategy would break this quietly: sealed
records would keep answering searches on the servers while disappearing locally.
If that day comes, removal has to become explicit.

The window is the gap between the court sealing a case and the next publication.
Closing it further means publishing more often, not a different mechanism.

### What is recorded
`meta.publicacao` keeps one row per publication, with the timestamp, the number of
decisions and which machine sent them. It lives outside `core` on purpose —
inside, the next swap would erase it. This is where the "last updated" shown to
the user comes from.

### Measured
107,828 decisions, over the private network:

```
development server   56s
production server    73s
```
