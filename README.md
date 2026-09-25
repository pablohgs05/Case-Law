# 5th Semester API - Database

<h2 align="center">Praxis | Case Law</h2>

<p align="center">
  <a href="#challenge">Challenge</a> •
  <a href="#solution">Solution</a> •
  <a href="#backlog">Product Backlog</a> •
  <a href="#sprints">Sprint Schedule</a> •
  <a href="#sprintdor">DoR and DoD</a> •
  <a href="#technologies">Technologies</a> •
  <a href="#branches">Branches and Commits</a> •
  <a href="#team">Team</a>
</p>

---

**Project Status** 🚧 Sprint 1 delivered  
**Documentation Folder** 📄 [documentation/](documentation/)  
**Project Video** 📽️ [Sprint 1 increment](https://www.youtube.com/watch?v=82bR--xO6Fs)  

Testing process: [unit and integration tests](TESTING.md).

---

## Challenge <a id="challenge"></a>

Brazilian case law is public, but it is not in one place. Each court publishes
its decisions on its own portal, with its own search, its own vocabulary and its
own way of naming a document. Someone researching a subject opens one portal at
a time, repeats the search in each, and copies what they find into a document of
their own.

That costs time, and it costs certainty. A decision found in a list is not yet
usable: before citing it, the researcher has to open the original on the court's
site and read it. When the list does not carry the address of the document, that
verification is done by hand — by case number, on the portal, one at a time.

Our academic partner brought this as the problem to solve: **searching decisions
from different courts as if they were one collection, without losing the link
back to the original.**

---

## Solution <a id="solution"></a>

A single search over decisions from every integrated court, where each result
keeps the address of its own document on the court's site.

| | |
|---|---|
| **One search, many courts** | 984,824 decisions from the STJ and the TJDFT, searched together |
| **Full-text in Portuguese** | accents and word endings do not matter: *acao* finds *ação*, *usucapiao* finds *usucapião* |
| **The terms, highlighted** | the excerpt shows why the decision matched |
| **Always the official source** | every result links to the document on the court's own site, and the screen says that the original prevails |
| **Filters that narrow** | court, judgment date, publication date, in any combination |
| **What the base holds** | coverage per court and period, so the reach of a search is known before it is trusted |

The reach today:

| Court | Decisions | Coverage |
|---|---|---|
| **STJ** — Superior Tribunal de Justiça | 876,996 | 19/02/1989 – 26/08/2026 |
| **TJDFT** — Tribunal de Justiça do Distrito Federal e dos Territórios | 107,828 | 17/09/2025 – 17/09/2026 |
| **Total** | **984,824** | **19/02/1989 – 17/09/2026** |

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

### Sprint Backlog

<p align="left">
  <a href="https://github.com/Praxis-Fatec/Case-Law/blob/main/documentation/sprints/sprint-1/sprint-1-backlog.md">
    <img src="https://img.shields.io/badge/Backlog%20Sprint%201-5B2C2B?style=for-the-badge&logo=github&logoColor=white" alt="Backlog da Sprint 1" />
  </a>
</p>

## Sprint Schedule <a id="sprints"></a>

| Sprint | Period | Goal | Documentation | Increment |
|---|---|---|---|---|
| **1** | 07/09/2026 – 27/09/2026 | Search decisions across courts, read them and check the reach of the base | [Backlog](documentation/sprints/sprint-1/sprint-1-backlog.md) · [DoR and DoD](documentation/sprints/Artefatos.md) | [Watch](https://www.youtube.com/watch?v=82bR--xO6Fs) |
| **2** | to be defined | — | — | — |
| **3** | to be defined | — | — | — |

---

## DoR and DoD <a id="sprintdor"></a>

The team's Definition of Ready, Definition of Done and the acceptance criteria
written for each User Story of the sprint:

<p align="left">
  <a href="documentation/sprints/Artefatos.md">
    <img src="https://img.shields.io/badge/DoR%20and%20DoD-5B2C2B?style=for-the-badge&logo=github&logoColor=white" alt="DoR and DoD" />
  </a>
</p>

Two rules there are ours, not inherited from the model, and they are the ones
that changed how the sprint ran:

- **A source is verified, never presumed.** A story that depends on a court or on
  a field only enters the sprint after someone has confirmed that the field
  exists and is reachable — not after someone assumed it does.
- **A link is not done until it opens.** A result that carries the address of a
  document is only finished when that address has been opened and shown to lead
  to the decision it claims. Two bugs of this sprint (SCRUM-94 and SCRUM-95)
  exist because the first version of this rule only checked that the identifier
  was there.

---

## Technologies <a id="technologies"></a>

**Frontend**

<p align="left">
  <img src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite" />
  <img src="https://img.shields.io/badge/React%20Router-CA4245?style=for-the-badge&logo=reactrouter&logoColor=white" alt="React Router" />
  <img src="https://img.shields.io/badge/Vitest-6E9F18?style=for-the-badge&logo=vitest&logoColor=white" alt="Vitest" />
  <img src="https://img.shields.io/badge/ESLint-4B32C3?style=for-the-badge&logo=eslint&logoColor=white" alt="ESLint" />
</p>

**Backend**

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic" />
  <img src="https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" alt="pytest" />
  <img src="https://img.shields.io/badge/Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black" alt="Ruff" />
  <img src="https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white" alt="uv" />
</p>

**Data**

<p align="left">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/pgvector-4169E1?style=for-the-badge" alt="pgvector" />
  <img src="https://img.shields.io/badge/dlt-2E8B57?style=for-the-badge&logo=dlthub&logoColor=white" alt="dlt" />
  <img src="https://img.shields.io/badge/SQLMesh-1E1E1E?style=for-the-badge" alt="SQLMesh" />
</p>

**Infrastructure**

<p align="left">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/nginx-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="nginx" />
  <img src="https://img.shields.io/badge/Tailscale-242424?style=for-the-badge&logo=tailscale&logoColor=white" alt="Tailscale" />
</p>

---

## Branches and Commits <a id="branches"></a>

**Two long-lived branches, and a short one for each task.**

| Branch | What it is |
|---|---|
| `main` | the project as it is presented: documentation and the delivered code |
| `dev` | what is integrated and published to the development environment |
| `producao` | what is published to production |

A task branch is opened from `dev`, named after its card, and closed by a Pull
Request back into `dev`. It is never pushed to directly from another task.

```
<type>/SCRUM-<number>-<what-it-does>

feat/SCRUM-91-stj-as-second-source
test/SCRUM-60-chart-agrees-with-search
bugfix/SCRUM-94-tjdft-link-opens-the-home
docs/SCRUM-43-sprint-video-and-readme-sections
```

**Why this and not trunk-based:** the published environments are deployed by the
branch they sit on. `dev` deploys to the development server on merge, `producao`
deploys to production on merge. Keeping them as branches makes the deploy a
reviewable event rather than a command someone runs.

**Commit messages** follow the same types, in the imperative:

```
<type>: <what the commit does>

feat: integrate filtered court volume chart
fix: ask the court list once per visit
test: hold the chart and the results to the same number
```

A commit says what it does to the product, not what was touched: *fix: ask the
court list once per visit*, not *fix: change HomePage.tsx*.

The protected branches are guarded by a workflow: a PR into `dev` or `producao`
only merges with the CI green.

---

## Team <a id="team"></a>

| Member | Role | GitHub | LinkedIn |
|---|---|---|---|
| **Giovana Zucareli** | Product Owner | [View Profile](//github.com/GiovanaZucareli) | [View Profile](//linkedin.com/in/giovana-zucareli-1aa205202) |
| **Pedro Ribeiro** | Scrum Master | [View Profile](//github.com/pedrohenribeiro) | [View Profile](//linkedin.com/in/pedrohenribeiro1) |
