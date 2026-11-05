"""
The scholarship that treats what a decision settled.

Two ways in. Given a decision, the works the matching suggested for it; given a
term, the collection itself. The second exists because the first is allowed to
find nothing — four decisions in five receive no suggestion — and a collection
nobody can search is a collection nobody can use.

Never the work, only the record of it and the link back. Open access is
permission to read, not permission to redistribute, and this is the endpoint
where forgetting that would cost the most.

Enrichment, never the critical path. A decision opens without this; the detail
endpoint does not call it. If the collection is not published in an
environment, this answers 503 and the screen shows the decision anyway.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE, two_examples

router = APIRouter(tags=["doctrine"])

SEARCH_CONFIG = "portugues_sem_acento"
QUERY = f"websearch_to_tsquery('{SEARCH_CONFIG}', %(term)s)"

# The work's own words, and nothing of the work itself. `resumo` is left out on
# purpose: it carries an abstract in a third of the records and a table of
# contents or an event note in the rest, and neither is ours to republish.
FIELDS = """
  d.repositorio,
  d.identificador_oai,
  d.titulo,
  d.titulos_alternativos,
  d.autores,
  d.assuntos,
  d.tipo,
  d.data,
  d.ano,
  d.idioma,
  d.publicacao,
  d.referencia,
  d.url_fonte
"""

# Ordering closes on the unique key. Without it PostgreSQL is free to return
# ties in any order, and a work can appear on two pages or on neither. The
# collection is small enough today that a test cannot provoke it — the planner
# reads six rows the same way every time — so the guarantee is asserted on the
# statement rather than on the answer, as `test_ordering` does for decisions.
TIEBREAK = "d.repositorio, d.identificador_oai"

RELATED_SQL = f"""
SELECT
  {FIELDS},
  s.nota,
  s.termos,
  s.casou_em
FROM core.decisao_doutrina AS s
JOIN core.doutrina AS d
  ON d.repositorio = s.repositorio
 AND d.identificador_oai = s.identificador_oai
WHERE s.fonte_codigo = %(source)s
  AND s.identificador_fonte = %(identifier)s
ORDER BY s.nota DESC, {TIEBREAK}
LIMIT %(limit)s
"""

DECISION_EXISTS_SQL = """
SELECT 1
FROM core.decisao
WHERE fonte_codigo = %(source)s
  AND identificador_fonte = %(identifier)s
"""

SEARCH_SQL = f"""
SELECT
  {FIELDS},
  TS_RANK_CD(d.busca, {QUERY}) AS relevancia
FROM core.doutrina AS d
WHERE d.busca @@ {QUERY}
ORDER BY TS_RANK_CD(d.busca, {QUERY}) DESC, {TIEBREAK}
LIMIT %(limit)s OFFSET %(offset)s
"""

SEARCH_COUNT_SQL = f"""
SELECT COUNT(*) AS total
FROM core.doutrina AS d
WHERE d.busca @@ {QUERY}
"""

WORK_EXAMPLE: dict[str, Any] = {
    "repository": "bdjur",
    "identifier": "oai:bdjur.stj.jus.br:2011/98958",
    "title": "A avaliação do regime jurídico da litigância de má-fé em Portugal",
    "alternative_titles": [
        "Evaluation of Portuguese legal framework on litigation in bad faith"
    ],
    "authors": ["Gouveia, Mariana França"],
    "subjects": ["Litigância de má-fé, Portugal", "Processo civil, Portugal"],
    "type": "Artigo",
    "date": "2014",
    "year": 2014,
    "language": "pt-br",
    "publication": "Revista de Processo",
    "reference": "Revista de Processo, São Paulo, v. 39, n. 231, p. 345-367, maio 2014.",
    "url": "https://bdjur.stj.jus.br/handle/2011/98958",
}

SUGGESTION_EXAMPLE: dict[str, Any] = {
    **WORK_EXAMPLE,
    "score": 9.3,
    "matched_on": ["litiganc", "ma-f"],
}


class Work(BaseModel):
    """One record from the collection. The work itself stays at the source."""

    repository: str = Field(
        description="Which collection holds it.", examples=["bdjur"]
    )
    identifier: str = Field(
        description="Identifier within that collection.",
        examples=["oai:bdjur.stj.jus.br:2011/98958"],
    )
    title: str = Field(description="As the library catalogued it.")
    alternative_titles: list[str] = Field(
        default_factory=list,
        description=(
            "Other titles on the same record, usually a translation. Empty for "
            "most of the collection — an empty list, never null."
        ),
    )
    authors: list[str] = Field(
        default_factory=list, description="In the order the record gives them."
    )
    subjects: list[str] = Field(
        default_factory=list,
        description=(
            "Keywords the cataloguer chose. Present on 54,8% of the collection, "
            "and empty rather than null on the rest."
        ),
    )
    type: str | None = Field(
        default=None, description="What kind of work it is.", examples=["Artigo"]
    )
    date: str | None = Field(
        default=None,
        description=(
            "When it was published, as the library wrote it. Text, not a date: "
            "`1976`, `2001-12` and `1997/1998` are all real values, and turning "
            "them into a date would invent a day nobody recorded."
        ),
        examples=["2014"],
    )
    year: int | None = Field(
        default=None,
        description="The same date reduced to a year, for sorting and filtering.",
        examples=[2014],
    )
    language: str | None = Field(default=None, examples=["pt-br"])
    publication: str | None = Field(
        default=None, description="Where it came out, when the record says."
    )
    reference: str | None = Field(
        default=None,
        description="The full bibliographic citation, ready to paste.",
    )
    url: str = Field(
        description="The permanent link to the record at the source.",
        examples=["https://bdjur.stj.jus.br/handle/2011/98958"],
    )

    model_config = {"json_schema_extra": {"example": WORK_EXAMPLE}}


class Suggestion(Work):
    """A work this decision's thesis was matched to, and why."""

    score: float = Field(
        description=(
            "How much the match weighs: the summed rarity, in judicial "
            "language, of the terms the thesis and the work share. It orders "
            "the list and nothing more — it was measured not to tell a useful "
            "suggestion from a useless one."
        ),
        examples=[9.3],
    )
    matched_on: list[str] = Field(
        description=(
            "The word stems that matched, strongest first. Not decoration: it "
            "is what lets a reader judge the suggestion without opening the "
            "work. Stems, not words — `ma-f` is *má-fé*."
        ),
        examples=[["litiganc", "ma-f"]],
    )

    model_config = {"json_schema_extra": {"example": SUGGESTION_EXAMPLE}}


class RelatedDoctrine(BaseModel):
    results: list[Suggestion] = Field(
        default_factory=list,
        description=(
            "Ordered by score. Empty for four decisions in five, which is the "
            "designed answer and not a failure: a procedural thesis has no "
            "subject matter to match, and a bad suggestion costs more than none."
        ),
    )


class DoctrineResults(BaseModel):
    total: int = Field(
        description="How many works match, beyond this page.", examples=[12]
    )
    page: int = Field(description="Which page this is, starting at 1.", examples=[1])
    page_size: int = Field(description="The page size that was applied.", examples=[20])
    results: list[Work]


def _work(row: DictRow) -> dict[str, Any]:
    return {
        "repository": row["repositorio"],
        "identifier": row["identificador_oai"],
        "title": row["titulo"],
        "alternative_titles": row["titulos_alternativos"] or [],
        "authors": row["autores"] or [],
        "subjects": row["assuntos"] or [],
        "type": row["tipo"],
        "date": row["data"],
        "year": row["ano"],
        "language": row["idioma"],
        "publication": row["publicacao"],
        "reference": row["referencia"],
        "url": row["url_fonte"],
    }


@router.get(
    "/decisions/{source}/{identifier}/doctrine",
    summary="Scholarship suggested for this decision",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        200: two_examples(
            (
                "matched",
                "The thesis shares distinctive terms with a work in the collection.",
                {"results": [SUGGESTION_EXAMPLE]},
            ),
            (
                "nothing to suggest",
                (
                    "Four decisions in five answer this way. It is the rule "
                    "working, not a failure, and it is never an error."
                ),
                {"results": []},
            ),
        ),
    },
)
def related_doctrine(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
    limit: Annotated[
        int,
        Query(ge=1, le=20, description="How many suggestions at most."),
    ] = 5,
) -> RelatedDoctrine:
    """
    The scholarship matched to this decision's thesis, strongest first.

    Each suggestion carries the link to the source and the terms that matched,
    so a reader can judge it without opening the work. The response never
    carries the work's text.

    A decision with nothing matched answers an empty list, not an error, and so
    does a decision that has no thesis at all. Only an identifier that is not
    in the collection answers 404.
    """
    # A NUL byte cannot be sent to PostgreSQL as text, and both parts arrive
    # from the URL. Refusing it here is the difference between "no such
    # decision" and a stack trace.
    if "\x00" in source or "\x00" in identifier:
        raise HTTPException(status_code=404, detail="Decision not found.")

    parameters = {"source": source, "identifier": identifier}

    with connection.cursor() as cursor:
        cursor.execute(DECISION_EXISTS_SQL, parameters)
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Decision not found.")

        cursor.execute(RELATED_SQL, {**parameters, "limit": limit})
        rows = cursor.fetchall()

    return RelatedDoctrine(
        results=[
            Suggestion(
                **_work(row),
                score=round(float(row["nota"]), 2),
                matched_on=list(row["casou_em"] or []),
            )
            for row in rows
        ]
    )


@router.get(
    "/doctrine",
    summary="Search the scholarship collection",
    responses=DATABASE_RESPONSES,
)
def search_doctrine(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="What to look for, over the title and the subjects.",
            examples=["litigância de má-fé"],
        ),
    ],
    page: Annotated[int, Query(ge=1, description="Which page, starting at 1.")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, description="How many works per page."),
    ] = 20,
) -> DoctrineResults:
    """
    Search the collection directly, over title and subject.

    The same `websearch_to_tsquery` and the same `portugues_sem_acento`
    configuration the decision search uses, over another table. The abstract is
    not searched: it exists on a third of the records and carries a table of
    contents or an event note as often as a summary, so including it would
    return works whose text never discusses the term.

    A page past the last one is an empty list with the same total, never an
    error.
    """
    page_size = min(page_size, settings.search_max_page_size)
    parameters = {
        "term": q,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }

    with connection.cursor() as cursor:
        cursor.execute(SEARCH_COUNT_SQL, parameters)
        row = cursor.fetchone()
        total = int(row["total"]) if row else 0

        cursor.execute(SEARCH_SQL, parameters)
        rows = cursor.fetchall()

    return DoctrineResults(
        total=total,
        page=page,
        page_size=page_size,
        results=[Work(**_work(row)) for row in rows],
    )
