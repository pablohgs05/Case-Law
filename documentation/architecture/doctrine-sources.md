# Doctrine sources

Which repositories of legal scholarship this project can harvest, what each one
answers today, and the rule that decides what may be collected at all.

Tested on **2026-10-24** and **2026-10-25**, from a residential connection in
Brazil, with an identified `User-Agent` and one request at a time. The figures
the sprint was planned on came from a test on **2026-10-05**; three of them no
longer hold, which is why this document exists rather than a line in a card.
Every count here is reproducible against the addresses it names.

---

## The rule, before the sources

This is the scope of the story and it does not depend on which source answers.

1. **Only sets the repository itself declares to be open access.** Not our
   judgement about a work — the library's own classification of it.
2. **Only metadata and the link back.** Never the full text, never the PDF.
3. **`dc:rights` is respected** wherever the record carries it.

The tool points at scholarship; it does not redistribute it. That holds even
for open access, because open to read is not the same as open to redistribute.

**Which of the two carries the weight, measured.** Over a sample of 798 records
read on 25/10/2026, `dc:rights` is present in **5,8%**. Requiring it would leave
94% of the open collection out, so the collection is the guarantee and the field
is the exception — and where the two disagree, the field wins. One record filed
in Acesso Aberto declares `Restricted access` in its own `dc:rights`, and it
does not enter the core. The rule is an allow list: an unknown rights statement
excludes the work rather than including it.

What the same sample says about the fields, which is what decides how doctrine
can be matched to a decision at all:

| Field | Coverage |
|---|---:|
| title, author, date, type, identifier, format | 100% |
| `dc:language` | 99,4% |
| `dc:publisher` | 74,6% |
| `dc:subject` | 54,8% |
| `dc:description` — the abstract | 31,8% |
| `dc:relation` | 16,9% |
| `dc:rights` | 5,8% |

---

## BDJur — Biblioteca Digital do STJ

| | |
|---|---|
| Endpoint | `https://bdjur.stj.jus.br/server/oai/request` |
| 2026-10-05 | OAI-PMH 2.0 working, 13 formats, records since 2004 |
| **2026-10-24** | **HTTP 403 — automated access refused** |

The response is a JavaScript challenge page, and it names its author:

> Verificação automática em andamento. Enable JavaScript and cookies to continue
> — **Coordenadoria de Segurança e Defesa Cibernética (CSID/STJ)**

Three consecutive requests, 403 each time. The refusal covers the **whole
host**, not the harvesting path: `/`, `/server/api` and `/oai/request` all
answer 403.

This is a deliberate measure, not an outage, and it is not to be worked around.

**It lets a person through.** Opened in a browser on 2026-10-24, the endpoint
answers normally, which confirms the challenge is doing what it is for rather
than refusing the public. What a browser read that day:

| | |
|---|---|
| Repository | BDJur, protocol 2.0, DSpace |
| **Contact** | **`bdjur@stj.jus.br`** |
| Earliest record | 2004-04-06 13:40:01 |
| Granularity | `YYYY-MM-DD hh:mm:ss` — incremental harvesting by `from`/`until` |
| Sets | 57 |

That contact is published by the protocol itself and belongs to the library,
not to the security team. It is the address to ask for harvesting access.

**Sets the sprint was planned on**, recorded here so the request to the STJ can
name them:

```
com_2011_2   Doutrina                    83.374 registros
col_2011_8   Artigos de Acesso Aberto    20.597 registros   ← 20.504 em 05/10
col_2011_9   Artigos de Acesso Restrito  ← never collected
```

Confirmed in the browser on 2026-10-24: the three codes still name the same
sets, and the open-access one has grown by 93 records since the planning test.
Of the 57 sets the repository publishes, these are the ones this story needs.

That the STJ separates open from restricted into distinct collections is what
settles the copyright question the client asked about: collecting only the
first is the library's classification, not ours.

> **One trap worth keeping.** The endpoint is `/server/oai/request`, not
> `/oai/request`. In DSpace 7 the shorter path answers HTTP 200 with the
> Angular shell — success-shaped, and not OAI-PMH.

---

## BDTD — now Oasisbr, of the IBICT

| | |
|---|---|
| Old endpoint | `https://bdtd.ibict.br/vufind/OAI/Server` → **HTTP 404** |
| OAI on the current host | `https://oasisbr.ibict.br/vufind/OAI/Server` → **HTTP 200, and not OAI** |
| **REST API on the current host** | `https://oasisbr.ibict.br/vufind/api/v1/search` → **HTTP 200, JSON, and it answers** |

The old address was returning 503 on 24/10; a day later it is a 404. The
address the client named is gone, not resting.

**The OAI path is challenged; another path is not.** `/vufind/OAI/Server`
answers 1.697 bytes of HTML titled "Verificando conexão | Oasisbr" — an
anti-bot challenge served with a success code, the same shape of trap as the
DSpace one above. An identified `User-Agent` and one request at a time do not
change it, which is what the subtask asked to be measured.

But Oasisbr runs VuFind, and VuFind publishes its own REST API at
`/vufind/api/v1/`. That path is not behind the challenge. It is a different
published interface, not a way around the first one: no browser string, no
cookie, no challenge solved. Asked politely, it answers.

The subtask also asked whether the IBICT documents a channel for institutional
harvesting. It could not be read: `ibict.br/.../oasisbr/` answers 200 with a
page titled "Estamos em manutenção". The API makes the question less urgent,
but it is still the right thing to ask for before collecting at scale.

**What it holds.** 6.593.376 records in all. Narrowing to open-access theses
and dissertations, and then to Law three different ways:

| How Law is narrowed | Doctoral theses | Master's dissertations |
|---|---:|---:|
| any field mentions "direito" | 33.289 | 102.589 |
| **subject contains "direito"** | **11.127** | **36.632** |
| title contains "direito" | 6.406 | 15.006 |

**47.759** by the middle row, which is the defensible one: the free-text count
sweeps in every thesis that mentions a right in passing, and the title count
misses the ones named after their subject matter.

**Open access is a field here, and it is filterable.** `eu_rights_str_mv`
carries the DRIVER vocabulary the repository network standardised on, and the
server facets on it. Over the 36.608 doctoral theses that mention "direito":

```
openAccess        33.289
embargoedAccess      328
restrictedAccess      13
(no value)         2.978
```

That is the same guarantee the BDJur gives through its collections, expressed
as a field instead: the classification belongs to the repository that deposited
the work, not to us. The 2.978 without a value are the case the rule already
answers — unknown rights excludes the work.

**No subject facet.** `topic_facet` is not offered, so there is no area to
filter by — Law is a text match, which is why the table above has three rows
instead of one.

**It also aggregates the BDJur, almost whole.** Oasisbr holds **75.405**
records under `institution:"STJ"`, against the 83.374 of the BDJur's Doutrina
set — about 90% of it, pointing back at the same `bdjur.stj.jus.br/handle/`
links.

The two corpora are not the same content — the STJ's 75.405 are the journal
articles of its own library, the 47.759 are theses and dissertations deposited
by universities — so a collector scoped to theses would not collide with 9.2.
One scoped by subject alone would, and would re-collect most of the BDJur
through a second door. Whichever Sprint 3 chooses, it has to say which.

**Verdict: it has a route, and it does not enter this sprint.** The reason is
not the challenge — it is that the route found is not the one the sprint was
planned on. The subtask assumed a source that entered would reuse the OAI-PMH
extractor from 9.2 "because the protocol is the same". It is not the same: this
is a JSON REST API with its own paging and its own field names, so it needs its
own connector. 47.759 open-access Law theses is the largest corpus of the three
and deserves its own story in Sprint 3, not a corner of this one.

---

## SciELO

| | |
|---|---|
| Old OAI endpoint | `https://www.scielo.br/oai/scielo-oai.php` → **HTTP 404, gone** |
| **Current API** | `https://articlemeta.scielo.org/api/v1/` → **HTTP 200, JSON** |

ArticleMeta is the replacement, and it answers. It is not OAI-PMH — it is a
REST API over the same corpus, with identifiers, journals and articles.

**What it holds for this project.** All 427 journals of the Brazilian
collection were read on 25/10/2026, one request at a time:

| ISSN | Journal | WoS area | Articles | Licence |
|---|---|---|---:|---|
| 2179-8966 | Revista Direito e Práxis | SOCIOLOGY | 1.014 | CC BY 4.0 |
| 1808-2432 | Revista Direito GV | LAW | 660 | CC BY 4.0 |
| 2177-7055 | Sequência (Florianópolis) | LAW | 421 | CC BY 4.0 |
| 2359-5639 | Revista de Investigações Constitucionais | LAW | 337 | CC BY 4.0 |
| 2525-510X | Revista Brasileira de Direito Processual Penal | LAW | 211 | CC BY 4.0 |
| 1806-6445 | Sur. Revista Internacional de Direitos Humanos | POLITICAL SCIENCE | 106 | **CC BY-NC 4.0** |
| 2179-8699 | Veredas do Direito | LAW | 88 | CC BY 4.0 |
| 2317-7721 | Revista de Direito da Cidade | LAW | 46 | CC BY 4.0 |
| | **Total** | | **2.883** | |

> **Correcting the earlier count.** This table says 8 journals and 2.883
> articles where the first version of this document said 6 and 2.125. The six
> counts it had were right; the set was not. *Sequência* is the UFSC law
> programme's journal and its title does not say so, and *Investigações
> Constitucionais* was missed by the title pattern.

**Which field finds a law journal: neither, alone.** The client asked whether
the Direito section can be filtered. It cannot, by one field:

| | Finds | Misses |
|---|---:|---|
| Study area `v441` | 59 journals, all "Applied Social Sciences" | nothing, and sweeps in economics, administration, communication |
| WoS area `v854` = LAW | 6 | *Direito e Práxis* (SOCIOLOGY) — the largest — and *Sur* (POLITICAL SCIENCE) |
| Title pattern | 7 | *Sequência*, whose title names no subject |

The union of the last two is the 8 above. A list of ISSNs, reviewed by a person,
is the honest way to scope this source.

### The licence, which the client asked to verify

Measured over **200 articles**, 25 per journal spread across each journal's
whole run:

```
175  CC BY 4.0      — 7 journals
 25  CC BY-NC 4.0   — Sur. Revista Internacional de Direitos Humanos
```

**They do vary by journal**, as the client suspected. None is a **ND**
licence, so none forbids derivative use; the one **NC** restricts commercial
use, which matters for a tool that may one day be sold and is the reason this
is recorded per journal rather than as "SciELO is Creative Commons".

**The licence is not in the metadata API.** `license`, `licenses` and
`permissions` come back null on every article in ArticleMeta's JSON, and the
journal's `v540` is empty on all 427. It lives only in the XML renderings:

```
GET /api/v1/article?collection=scl&code=<code>&format=xmlwos
  → <permissions><license license-type="open-access"
       href="http://creativecommons.org/licenses/by/4.0/">
```

So respecting the licence per work costs one extra request per article — and
`format=sps` returns 83 KB, the article's full text, which is the one thing this
project must not store.

**Verdict: reachable, licensed, and small.** 2.883 articles against the 20.597
of the BDJur's open collection is **14%**, and against its whole Doutrina set
**3,5%**. It does not enter this sprint: its OAI endpoint is gone, so it does
not reuse the 9.2 extractor either, and the volume does not pay for a second
connector while the BDJur's own 20.597 are not yet matched to a decision. The
route and the licences are written here so Sprint 3 starts with them.

---

## The decision

**All three sources have a route. Only the BDJur enters this sprint.**

| Source | Route found | Law records, open access | In this sprint |
|---|---|---:|---|
| **BDJur** | OAI-PMH, `/server/oai/request` — 403 to a program, open to a person | 20.597 | **Yes**, from pages saved by hand until harvesting access is granted |
| Oasisbr | VuFind REST API, `/vufind/api/v1/` — the OAI path is challenged | 47.759 | No |
| SciELO | ArticleMeta REST, `/api/v1/` — the OAI endpoint is gone | 2.883 | No |

"Does not enter" is a result, not an omission, and here is what it rests on.

**The assumption that made the other two cheap does not hold.** The subtask
planned for a source that entered to reuse the OAI-PMH extractor from 9.2,
"because the protocol is the same". Measured, it is not: the BDTD's OAI path is
behind a challenge and only its JSON API answers, and SciELO's OAI endpoint
returns 404. Each would need a connector of its own, which is the cost the plan
did not price.

**The sprint is already over capacity, by its own arithmetic.** 84 points in
380 hours, against Sprint 1's 36 points in 288 hours with one more person. The
plan's own cut names this story: *"a 113 só com o BDJur"*.

**And the BDJur's own 20.597 records are not yet matched to a single decision.**
That is subtask 9.4, and it is the part that turns a collection into a feature.
A second source before the first one is useful adds corpus, not value.

### What Sprint 3 starts with

Written here so none of it has to be measured again:

- **Oasisbr** is the biggest of the three — 47.759 open-access Law theses and
  dissertations — and the one the client wanted for theses. Its rights field,
  `eu_rights_str_mv`, is standard and filterable server-side. Scope it to
  theses and dissertations and it does not overlap 9.2; scope it by subject
  alone and it re-collects 75.405 BDJur records through a second door.
- **SciELO** is scoped by a reviewed list of 8 ISSNs, because no single field
  identifies a law journal. Its licences vary — 7 journals CC BY, *Sur*
  CC BY-NC — and the licence is only in the `xmlwos` rendering, one extra
  request per article.
- **The BDJur** needs the e-mail to `bdjur@stj.jus.br` answered. Until then the
  collector reads saved pages, and the day it is answered the same code reads
  the endpoint.

What does not change for any of them is the rule at the top: declared-open sets
only, metadata and the link only, rights respected wherever the record states
them.
