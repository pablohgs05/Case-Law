import html
import re
import unicodedata
from datetime import date
from html.parser import HTMLParser
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection
from app.ementa import split as split_ementa
from app.errors import (
    DATABASE_RESPONSES,
    MALFORMED,
    NOT_FOUND_RESPONSE,
    two_examples,
)

router = APIRouter(tags=["search"])

SEARCH_CONFIG = "portugues_sem_acento"
MAX_SNIPPET_WORDS = 38
MAX_SNIPPET_FRAGMENTS = 2
SNIPPET_DELIMITER = " … "

QUERY = f"websearch_to_tsquery('{SEARCH_CONFIG}', %(term)s)"
MATCH = f"ementa_busca @@ {QUERY}"

SNIPPET_OPTIONS = (
    f"StartSel=<mark>, StopSel=</mark>, "
    f"MaxWords={MAX_SNIPPET_WORDS}, "
    f"MinWords={MAX_SNIPPET_WORDS - 16}, "
    f"MaxFragments={MAX_SNIPPET_FRAGMENTS}, "
    "FragmentDelimiter=' … '"
)

SNIPPET = f"""
ts_headline(
    '{SEARCH_CONFIG}', ementa, {QUERY},
    %(snippet_options)s
)
"""

FULL_HIGHLIGHT = f"""
ts_headline(
    '{SEARCH_CONFIG}', ementa, {QUERY},
    'StartSel=<mark>, StopSel=</mark>, HighlightAll=TRUE'
)
"""

Order = Literal["relevance", "date"]
DEFAULT_ORDER: Order = "relevance"

# Both end in identificador_fonte so a page boundary never splits a tie and
# repeats or drops a decision between pages.
ORDERINGS: dict[Order, str] = {
    "relevance": f"""
ORDER BY
    ts_rank(ementa_busca, {QUERY}) DESC,
    data_referencia DESC,
    identificador_fonte DESC
""",
    "date": """
ORDER BY
    data_referencia DESC,
    identificador_fonte DESC
""",
}


def _filters_sql(
    tribunals: list[str],
    date_from: date | None,
    date_to: date | None,
    published_from: date | None = None,
    published_to: date | None = None,
) -> str:
    """
    The optional narrowing, appended to the text match. The count and the page
    are built from the same string, so the total can never describe a different
    set than the one being paged through.

    The publication period reads `data_publicacao` alone, with no fallback: a
    decision the court never dated as published cannot be said to fall inside
    it, and a comparison with NULL is never true, so it is left out.
    """
    clauses: list[str] = []
    if tribunals:
        clauses.append("tribunal_sigla = ANY(%(tribunais)s)")
    if date_from is not None:
        clauses.append("data_referencia >= %(date_from)s")
    if date_to is not None:
        clauses.append("data_referencia <= %(date_to)s")
    if published_from is not None:
        clauses.append("data_publicacao >= %(published_from)s")
    if published_to is not None:
        clauses.append("data_publicacao <= %(published_to)s")
    return "".join(f" AND {clause}" for clause in clauses)


def _count_sql(filters: str = "") -> str:
    return f"SELECT COUNT(*) AS total FROM core.decisao WHERE {MATCH}{filters}"


def _page_sql(filters: str = "", ordering: str = "") -> str:
    ordering = ordering or ORDERINGS[DEFAULT_ORDER]
    return f"""
WITH pagina AS (
    SELECT fonte_codigo, identificador_fonte
    FROM core.decisao
    WHERE {MATCH}{filters}
    {ordering}
    LIMIT %(limit)s OFFSET %(offset)s
)
SELECT
    decisao.fonte_codigo,
    decisao.identificador_fonte,
    decisao.tribunal_sigla,
    decisao.processo,
    decisao.orgao_julgador,
    decisao.relator,
    decisao.data_referencia,
    decisao.turma_recursal,
    decisao.url_fonte,
    decisao.link_valido,
    decisao.ementa,
    {SNIPPET} AS snippet
FROM pagina
JOIN core.decisao USING (fonte_codigo, identificador_fonte)
{ordering}
"""


# Without filters and in the default order, the exact statements the search ran
# before either existed.
COUNT_SQL = _count_sql()
PAGE_SQL = _page_sql()

DETAIL_SQL = """
SELECT
    fonte_codigo,
    identificador_fonte,
    tribunal_sigla,
    processo,
    orgao_julgador,
    relator,
    classe_cnj,
    data_julgamento,
    data_publicacao,
    data_referencia,
    ementa,
    decisao_texto,
    turma_recursal,
    possui_inteiro_teor,
    url_fonte,
    link_valido
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

HIGHLIGHT_SQL = f"""
SELECT {FULL_HIGHLIGHT} AS highlighted
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""


class DecisionBase(BaseModel):
    source: str = Field(
        description="Which collection the decision came from.",
        examples=["tjdft-jurisdf"],
    )
    identifier: str = Field(
        description="The identifier the court itself uses.",
        examples=["2084700"],
    )
    court: str = Field(description="Court abbreviation.", examples=["TJDFT"])
    case_number: str | None = Field(
        description="Case number in the national format.",
        examples=["0738852-37.2024.8.07.0003"],
    )
    judging_body: str | None = Field(
        description="The panel that decided.",
        examples=["1ª TURMA CÍVEL"],
    )
    reporting_judge: str | None = Field(
        description="The judge who wrote the opinion.",
        examples=["FABRÍCIO FONTOURA BEZERRA"],
    )
    decided_on: date = Field(
        description="Judgement date, or publication date when the first is absent.",
        examples=["2026-01-28"],
    )
    small_claims: bool = Field(
        description="Whether it comes from a small claims appellate panel.",
        examples=[False],
    )
    source_url: str = Field(
        description="The decision on the court's own site, which always prevails.",
        examples=["https://jurisdf.tjdft.jus.br/detalhes/2084700"],
    )
    source_url_reachable: bool | None = Field(
        description=(
            "Whether the link was found to reach a document the last time the "
            "load checked. `null` means nobody has checked it yet, which is not "
            "the same as broken. Never checked while answering this request."
        ),
        examples=[True],
    )


class DecisionMatch(DecisionBase):
    snippet: str = Field(
        description=(
            "The part of the ementa that matched, with every hit wrapped in "
            "`<mark>`. Accents survive: only the matching ignores them."
        ),
        examples=["Ilícito contratual. <mark>Dano</mark> <mark>moral</mark>."],
    )


# The one response the documentation shows. A test keeps it carrying every
# field the schema has, so it cannot fall behind as the response grows.
STRUCTURED_EXAMPLE: dict[str, Any] = {
    "source": "tjdft-jurisdf",
    "identifier": "2119440",
    "court": "TJDFT",
    "case_number": "0712598-03.2019.8.07.0003",
    "judging_body": "3ª TURMA CÍVEL",
    "reporting_judge": "JOÃO EGMONT",
    "decided_on": "2026-06-11",
    "small_claims": False,
    "source_url": "https://jurisdf.tjdft.jus.br/detalhes/2119440",
    "source_url_reachable": True,
    "class_code": 1116,
    "judged_on": "2026-06-11",
    "published_on": "2026-06-18",
    "summary": (
        "PROCESSUAL CIVIL E TRIBUTÁRIO. EXECUÇÃO FISCAL. "
        "<mark>PRESCRIÇÃO</mark> INTERCORRENTE. I. CASO EM EXAME 1. "
        "Apelação interposta contra sentença que julgou extinta a "
        "execução fiscal. II. QUESTÃO EM DISCUSSÃO 2. Definir o termo "
        "inicial da suspensão. III. RAZÕES DE DECIDIR 3. O prazo corre "
        "da ciência da primeira diligência infrutífera. IV. DISPOSITIVO "
        "4. Apelação conhecida e desprovida."
    ),
    "outcome": "APELAÇÃO CONHECIDA E DESPROVIDA. UNÂNIME.",
    "full_text_available": True,
    "sections": {
        "headnote": (
            "PROCESSUAL CIVIL E TRIBUTÁRIO. EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE."
        ),
        "case": (
            "1. Apelação interposta contra sentença que julgou "
            "extinta a execução fiscal."
        ),
        "question": "2. Definir o termo inicial da suspensão.",
        "reasoning": (
            "3. O prazo corre da ciência da primeira diligência infrutífera."
        ),
        "ruling": "4. Apelação conhecida e desprovida.",
    },
}


class EmentaSections(BaseModel):
    """
    The four sections of the national court council's shape, as the court wrote
    them. The labels are left out: each field is the section's own text.
    """

    headnote: str = Field(
        description=(
            "The keyword block every ementa opens with, before the first "
            "section. Not one of the four, and kept because it is text the "
            "court wrote."
        ),
        examples=["DIREITO CIVIL. APELAÇÃO CÍVEL. RECURSO CONHECIDO E PROVIDO."],
    )
    case: str = Field(
        description="What was judged.",
        examples=["1. Apelação interposta contra sentença de improcedência."],
    )
    question: str = Field(
        description="What had to be decided.",
        examples=["2. Definir se houve falha na prestação do serviço."],
    )
    reasoning: str = Field(
        description="Why it was decided that way.",
        examples=["3. A falha ficou demonstrada pela prova documental."],
    )
    ruling: str = Field(
        description="What was decided, and the thesis when the court states one.",
        examples=["4. Recurso conhecido e provido."],
    )


class Decision(DecisionBase):
    class_code: int | None = Field(
        description="Case class, as the national court council codes it.",
        examples=[12394],
    )
    judged_on: date | None = Field(description="When the panel decided.")
    published_on: date | None = Field(description="When it reached the gazette.")
    summary: str = Field(
        description=(
            "The ementa in full: the legal thesis, as the court wrote it. "
            "Always the whole text — a search term that matched by stem and "
            "appears nowhere literally still gets the judgement, not an "
            "opening. With `q`, hits come wrapped in `<mark>` and the rest is "
            "HTML-escaped, so render it as HTML; without `q` it is the court's "
            "own text, unescaped. 146 of 107.828 ementas carry a character that "
            "escaping changes, so a screen that renders one path as HTML must "
            "render the other as text."
        ),
        examples=[
            (
                "PROCESSUAL CIVIL. EXECUÇÃO FISCAL. <mark>PRESCRIÇÃO</mark> "
                "INTERCORRENTE. I. CASO EM EXAME 1. Apelação interposta contra "
                "sentença que julgou extinta a execução fiscal."
            )
        ],
    )
    outcome: str | None = Field(
        description="The operative part, when the court records it separately.",
        examples=["ADMITIR. JULGAR IMPROCEDENTE A REVISÃO CRIMINAL. UNÂNIME."],
    )
    full_text_available: bool = Field(
        description="Whether the court offers the complete document."
    )
    sections: EmentaSections | None = Field(
        description=(
            "The ementa split into the four sections the national court council "
            "asks for, or `null` when it is written as free prose — which is "
            "how the two cases are told apart. 78,9% of the collection splits. "
            "Always read from the court's own text, so a search term never "
            "changes the answer: `summary` carries the highlighting, these "
            "carry the text."
        ),
    )

    model_config = {"json_schema_extra": {"example": STRUCTURED_EXAMPLE}}


class SearchResults(BaseModel):
    total: int = Field(
        description="How many decisions match, beyond the current page.",
        examples=[1847],
    )
    page: int = Field(description="Which page this is, starting at 1.", examples=[1])
    page_size: int = Field(description="How many results per page.", examples=[20])
    results: list[DecisionMatch]


def _base_fields(row: DictRow) -> dict[str, Any]:
    return {
        "source": row["fonte_codigo"],
        "identifier": row["identificador_fonte"],
        "court": row["tribunal_sigla"],
        "case_number": row["processo"],
        "judging_body": row["orgao_julgador"],
        "reporting_judge": row["relator"],
        "decided_on": row["data_referencia"],
        "small_claims": row["turma_recursal"],
        "source_url": row["url_fonte"],
        "source_url_reachable": row["link_valido"],
    }


class _MarkHTMLNormalizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "mark":
            self._parts.append("<mark>")
        else:
            self._parts.append(f"&lt;{tag}&gt;")

    def handle_endtag(self, tag: str) -> None:
        if tag == "mark":
            self._parts.append("</mark>")
        else:
            self._parts.append(f"&lt;/{tag}&gt;")

    def handle_data(self, data: str) -> None:
        self._parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def get_value(self) -> str:
        return "".join(self._parts)


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def _is_exact_phrase_query(query: str | None) -> bool:
    if query is None:
        return False
    stripped = query.strip()
    return len(stripped) >= 2 and stripped.startswith('"') and stripped.endswith('"')


def _normalize_highlighted_text(value: str | None, query: str | None = None) -> str:
    if value is None:
        return ""

    text = value.strip()
    if not text:
        return ""

    parser = _MarkHTMLNormalizer()
    parser.feed(text)
    parser.close()
    normalized = parser.get_value()
    normalized = re.sub(r"<mark>\s*</mark>", "", normalized)

    if query is not None and _is_exact_phrase_query(query):
        phrase = query.strip()[1:-1].strip()
        if not phrase:
            return normalized

        goal = _fold_text(phrase)
        pattern = re.compile(r"(?s)(<mark>.*?</mark>(?:\s*<mark>.*?</mark>)*)")
        for match in pattern.finditer(normalized):
            content = re.sub(r"</?mark>", "", match.group(1)).strip()
            content = re.sub(r"\s+", " ", content)
            if _fold_text(content) == goal:
                normalized = (
                    normalized[: match.start()]
                    + f"<mark>{content}</mark>"
                    + normalized[match.end() :]
                )
                break

        normalized = re.sub(r"</mark>\s*<mark>", " ", normalized)
        normalized = re.sub(r"<mark>\s+", "<mark>", normalized)
        normalized = re.sub(r"\s+</mark>", "</mark>", normalized)

    return normalized


def _fallback_ementa_start(ementa: str | None) -> str:
    """
    The opening of the ementa, for when the match is by stem and there is no
    literal term for `ts_headline` to mark.

    Trimmed by word count, not by sentence. These ementas open with short
    headnote sentences in caps, so the first two sentences come to under 80
    characters in 91% of the collection — a card with nothing to read — while a
    single long sentence runs to 3.590.
    """
    return " ".join((ementa or "").split()[:MAX_SNIPPET_WORDS])


def _safe_snippet(raw: str | None, ementa: str | None, query: str | None = None) -> str:
    snippet = (raw or "").strip()
    if snippet:
        normalized = _normalize_highlighted_text(snippet, query)
        if "<mark>" in normalized:
            return normalized

    return _fallback_ementa_start(ementa)


INVERTED_RANGE = "date_from must be less than or equal to date_to."
INVERTED_PUBLICATION_RANGE = (
    "published_from must be less than or equal to published_to."
)

# The search fails with 400 in two ways, and a caller handles them differently:
# one is a value the database cannot read, the other a range that is backwards.
SEARCH_RESPONSES: dict[int | str, dict[str, Any]] = {
    **DATABASE_RESPONSES,
    400: {
        **DATABASE_RESPONSES[400],
        "description": (
            "A parameter carries something the database cannot read, or a "
            "period ends before it starts: `date_from` after `date_to`, or "
            "`published_from` after `published_to`."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "malformed": {"value": {"detail": MALFORMED}},
                    "inverted range": {"value": {"detail": INVERTED_RANGE}},
                    "inverted publication range": {
                        "value": {"detail": INVERTED_PUBLICATION_RANGE}
                    },
                }
            }
        },
    },
}


@router.get(
    "/decisions",
    summary="Search decisions by term, court and date",
    responses=SEARCH_RESPONSES,
)
def search_decisions(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description=(
                'What to look for. `termo` matches every word, `"frase exata"` '
                "matches the sequence, `um OR outro` matches either, and `-termo` "
                "excludes. Accents are ignored."
            ),
            examples=["dano moral"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(
            description=(
                "Only decisions from this court, by its abbreviation exactly as "
                "`court` answers it (`TJDFT`, not `tjdft`). Repeat the parameter "
                "for several — `tribunal=TJDFT&tribunal=STJ` — and a decision "
                "from any of them is returned. Blank and repeated values are "
                "ignored. An abbreviation with no decisions answers `total: 0`, "
                "not an error. Omitted, every court is searched."
            ),
            examples=[["TJDFT"], ["TJDFT", "STJ"]],
        ),
    ] = None,
    date_from: Annotated[
        date | None,
        Query(
            description=(
                "Earliest `decided_on` to return, as `YYYY-MM-DD`. Inclusive: a "
                "decision dated this very day is returned. Alone, the range is "
                "open at the end."
            ),
            examples=["2026-03-01"],
        ),
    ] = None,
    date_to: Annotated[
        date | None,
        Query(
            description=(
                "Latest `decided_on` to return, as `YYYY-MM-DD`. Inclusive: a "
                "decision dated this very day is returned. Alone, the range is "
                "open at the start. The same day in both returns that one day."
            ),
            examples=["2026-03-31"],
        ),
    ] = None,
    published_from: Annotated[
        date | None,
        Query(
            description=(
                "Earliest publication date to return, as `YYYY-MM-DD`, compared "
                "with the date the decision reached the gazette alone. "
                "Inclusive. Decisions with no recorded publication date are "
                "left out whenever this or `published_to` is sent."
            ),
            examples=["2026-03-01"],
        ),
    ] = None,
    published_to: Annotated[
        date | None,
        Query(
            description=(
                "Latest publication date to return, as `YYYY-MM-DD`. Inclusive. "
                "Alone, the period is open at the start."
            ),
            examples=["2026-03-31"],
        ),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, description="Results per page.")] = 20,
    order: Annotated[
        Order,
        Query(
            description=(
                "`relevance` puts the closest match first, `date` the most "
                "recent. Both break ties the same way, so a decision never "
                "moves between pages."
            ),
        ),
    ] = DEFAULT_ORDER,
) -> SearchResults:
    """
    Search the ementa of every collected decision.

    Each result carries the passage that matched rather than the whole ementa,
    which runs to several thousand characters. Open a decision to read it whole.

    The total counts every match, not only this page, so a screen can say how
    many decisions exist before paging through them. With filters it counts
    every match inside them, on every page.

    `tribunal`, `date_from`, `date_to`, `published_from` and `published_to` are
    optional and narrow the search together: a result matches `q` **and** comes
    from one of the courts **and** falls within every period sent.

    There are two periods. `date_from`/`date_to` compare `decided_on` — the
    judgement date, or the publication date when the court did not record the
    first — so a result never falls outside the range the screen asked for.
    `published_from`/`published_to` compare the publication date alone, and a
    decision without one is left out while either is sent.

    Without filters, every court and every date:

        GET /decisions?q=dano+moral

    Combined — the exact phrase, from either of two courts, in March 2026 with
    both the 1st and the 31st included (one line, broken here to fit):

        GET /decisions?q=%22dano+moral%22&tribunal=TJDFT&tribunal=STJ
                      &date_from=2026-03-01&date_to=2026-03-31

    Judged in 2026 and published in March of it:

        GET /decisions?q=dano+moral&date_from=2026-01-01&date_to=2026-12-31
                      &published_from=2026-03-01&published_to=2026-03-31

    A date that is not a real `YYYY-MM-DD` day answers 422, like any malformed
    parameter. A period that ends before it starts answers 400: an empty range
    is almost always a mistake, and saying so beats an empty result.
    """
    page_size = min(page_size, settings.search_max_page_size)

    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail=INVERTED_RANGE)

    if (
        published_from is not None
        and published_to is not None
        and published_from > published_to
    ):
        raise HTTPException(status_code=400, detail=INVERTED_PUBLICATION_RANGE)

    tribunais = list(
        dict.fromkeys(value.strip() for value in tribunal or [] if value.strip())
    )

    parameters: dict[str, Any] = {
        "term": q,
        "snippet_options": SNIPPET_OPTIONS,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if tribunais:
        parameters["tribunais"] = tribunais
    if date_from is not None:
        parameters["date_from"] = date_from
    if date_to is not None:
        parameters["date_to"] = date_to
    if published_from is not None:
        parameters["published_from"] = published_from
    if published_to is not None:
        parameters["published_to"] = published_to

    filters = _filters_sql(tribunais, date_from, date_to, published_from, published_to)

    with connection.cursor() as cursor:
        cursor.execute(_count_sql(filters), parameters)
        total = int((cursor.fetchone() or {"total": 0})["total"])

        rows: list[DictRow] = []
        if total:
            cursor.execute(_page_sql(filters, ORDERINGS[order]), parameters)
            rows = cursor.fetchall()

    return SearchResults(
        total=total,
        page=page,
        page_size=page_size,
        results=[
            DecisionMatch(
                **_base_fields(row),
                snippet=_safe_snippet(row.get("snippet"), row.get("ementa"), q),
            )
            for row in rows
        ],
    )


def _sections(ementa: str | None) -> EmentaSections | None:
    parts = split_ementa(ementa)
    if parts is None:
        return None

    return EmentaSections(
        headnote=parts.headnote.strip(),
        case=parts.case.text.strip(),
        question=parts.question.text.strip(),
        reasoning=parts.reasoning.text.strip(),
        ruling=parts.ruling.text.strip(),
    )


@router.get(
    "/decisions/{source}/{identifier}",
    summary="Read one decision in full",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        200: two_examples(
            (
                "structured",
                "Written in the four sections, which 78,9% of the collection is.",
                STRUCTURED_EXAMPLE,
            ),
            (
                "free prose",
                (
                    "Not written in them: `sections` is null and `summary` is "
                    "all there is to read."
                ),
                {**STRUCTURED_EXAMPLE, "sections": None},
            ),
        ),
    },
)
def read_decision(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
    q: Annotated[
        str | None,
        Query(
            min_length=2,
            description="The search that led here, to highlight it in the ementa.",
        ),
    ] = None,
) -> Decision:
    """
    Read a single decision, ementa included.

    Pass the search term that led here and the ementa comes back with every hit
    wrapped in `<mark>`, so the reader lands on what they were looking for.
    """
    # A NUL byte cannot be sent to PostgreSQL as text, and an identifier arrives
    # from the URL, so it is whatever the caller typed. Refusing it here is the
    # difference between "no such decision" and a stack trace.
    if "\x00" in source or "\x00" in identifier:
        raise HTTPException(status_code=404, detail="Decision not found.")

    parameters = {"source": source, "identifier": identifier}

    with connection.cursor() as cursor:
        cursor.execute(DETAIL_SQL, parameters)
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found.")

        # `HighlightAll=TRUE` returns the ementa entire, marked where the term
        # hit and untouched where it did not, so there is nothing to fall back
        # to. Trimming here would hand a reading screen the first few lines of a
        # judgement, which is what the search snippet is for.
        summary = row["ementa"]
        if q:
            cursor.execute(HIGHLIGHT_SQL, {**parameters, "term": q})
            highlighted = cursor.fetchone()
            if highlighted:
                summary = _normalize_highlighted_text(highlighted["highlighted"], q)

    return Decision(
        **_base_fields(row),
        class_code=row["classe_cnj"],
        judged_on=row["data_julgamento"],
        published_on=row["data_publicacao"],
        summary=summary,
        outcome=row["decisao_texto"],
        full_text_available=row["possui_inteiro_teor"],
        sections=_sections(row["ementa"]),
    )
