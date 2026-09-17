# 5th Semester API - Database

<h2 align="center">Praxis | Case Law</h2>

<p align="center">
  <a href="#challenge">Challenge</a> •
  <a href="#solution">Solution</a> •
  <a href="#backlog">Product Backlog</a> •
  <a href="#sprints">Sprint Schedule</a> •
  <a href="#sprintdor">DoR and DoD</a> •
  <a href="#technologies">Technologies</a> •
  <a href="#environment">Environment</a> •
  <a href="#branches">Branches and Commits</a> •
  <a href="#burndown">Burn Down</a> •
  <a href="#team">Team</a> •
  <a href="#manual">User Manual</a>
</p>

---

**Project Status** 🚧 In progress  
**Documentation Folder** 📄 Available in the repository  
**Project Video** 📽️ Not started  

Testing process: [unit tests](TESTING.md).

---

## Development Environment <a id="environment"></a>

Only the database runs in Docker. The backend, the frontend and the pipeline run
natively, so hot reload and the debugger keep working.

```bash
docker compose up -d      # start the database
docker compose down       # stop it, keeping the data
docker compose down -v    # stop it and erase the data
```

It works with no setup: every value has a default. Copy `.env.example` to `.env`
only if you need to change the port or the credentials.

| Service | Port | Image |
|---|---|---|
| PostgreSQL | 5432 | `pgvector/pgvector:pg17` |

The image is not the official `postgres:17` on purpose — that one does not ship
`pgvector`. On first start, `infra/postgres/init.sql` creates three extensions:

| Extension | What it gives us |
|---|---|
| `pg_trgm` | search that tolerates typing errors: *usucapiao* finds *usucapião* |
| `unaccent` | accents stop mattering: *acao* finds *ação* |
| `vector` | vector column and distance operators, for semantic search later |

The init script only runs when the database is created. If you already have the
volume and need to replay it, run `docker compose down -v` first — that erases
the data.

Each part has its own instructions: [backend](backend/README.md) ·
[frontend](frontend/README.md) · [pipeline](pipeline/README.md)

---

## Product Backlog <a id="backlog"></a>

### 1. Profiles Used in User Stories

The profiles represent who receives value from the feature. They do not indicate who will be responsible for the development.

| Profile | Role in the Product |
|---|---|
| **Legal Analyst** | Researches subjects, filters results, organizes documents, and prepares analyses |
| **Lawyer** | Evaluates if a decision can support a case, a legal document, or a legal strategy |
| **Legal Manager** | Observes volumes, trends, and comparisons to support legal department decisions |
| **Magistrate** | Consults decisions and verifies coverage and reliability before using an information |

### 2. Product Backlog Table

| Rank | Priority | User Story | Estimate | Sprint |
|---|---|---|---|---|
| 1 | High | As a legal analyst, I want to search decisions by exact term or phrase, to locate rulings without needing to open each court's portal. | 8 | 1 |
| 2 | High | As a legal analyst, I want to see the results with an excerpt of the syllabus and a link to the official source, to verify the information before citing it. | 5 | 1 |
| 3 | High | As a legal analyst, I want to filter by court and period, to restrict the search to the relevant scope. | 5 | 1 |
| 4 | High | As a lawyer, I want to open the details of a decision with the rapporteur, judging body, dates, and complete syllabus, to evaluate if it fits my case. | 5 | 1 |
| 5 | High | As a legal manager, I want to see the volume of decisions by court, to know where the topic is concentrated. | 5 | 1 |
| 6 | High | As a legal analyst, I want to sort the results by relevance or date, to see the most pertinent or recent content first. | 3 | 1 |
| 7 | High | As a legal analyst, I want to navigate between result pages, to browse a large scope without losing my position. | 3 | 1 |
| 8 | High | As a magistrate, I want to see how many documents and courts the database covers and what period is available, to know the search's reach before trusting the result. | 2 | 1 |
| 9 | Medium | As a legal manager, I want to see the volume evolution over time, to identify judgment trends. | 8 | 2 |
| 10 | Medium | As a lawyer, I want to see the proportion between appeals granted, partially granted, and denied, to understand the historical results of the scope. | 8 | 2 |
| 11 | Medium | As a legal analyst, I want to filter by judging body, rapporteur, and procedural class, to refine the search. | 5 | 2 |
| 12 | Medium | As a legal analyst, I want to open the list of documents that make up each indicator, to verify the number at the source. | 5 | 2 |
| 13 | Medium | As a lawyer, I want to know if the decision was unanimous or by majority, to evaluate the degree of consensus on the topic. | 3 | 2 |
| 14 | Medium | As a legal analyst, I want to export the scope with the applied filters and references, to use it in a report. | 5 | 2 |
| 15 | Medium | As a legal manager, I want to compare courts side-by-side, to identify differences in rulings on the same topic. | 13 | 3 |
| 16 | Medium | As a magistrate, I want to see the status of each source and the date of the last collection, to evaluate the scope's reliability. | 3 | 3 |
| 17 | Medium | As a legal analyst, I want to save a search, to resume the investigation without reapplying filters. | 5 | 3 |
| 18 | Medium | As a legal manager, I want to see the concentration by judging body and rapporteur, to understand where and by whom the topic is decided. | 5 | 3 |
| 19 | Low | As a lawyer, I want to see the laws, articles, and precedents cited in the decision, to access its legal foundation. | 8 | 3 |
| 20 | Low | As a lawyer, I want to see decisions semantically close to the one I am reading, to expand the search. | 13 | 3 |
| 21 | Low | As a legal analyst, I want to report an incorrect classification, to contribute to the database's quality. | 3 | 3 |
| 22 | Low | As a lawyer, I want to identify divergences between panels of the same court, to evaluate how distribution might influence a judgment. | 13 | TBD |
| 23 | Low | As a lawyer, I want to locate decisions contrary to the one I am reading, to anticipate the opposing party's arguments. | 21 | TBD |

---

## Team <a id="team"></a>

| Member | Role | GitHub | LinkedIn |
|---|---|---|---|
| **Giovana Zucareli** | Product Owner | [View Profile](//github.com/GiovanaZucareli) | [View Profile](//linkedin.com/in/giovana-zucareli-1aa205202) |
| **Pedro Ribeiro** | Developer | [View Profile](//github.com/pedrohenribeiro) | [View Profile](//linkedin.com/in/pedrohenribeiro1) |
