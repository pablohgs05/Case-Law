import html
import re
import unicodedata
from datetime import date
from html.parser import HTMLParser
from typing import Annotated, Any, Literal, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection
from app.ementa import split as split_ementa
from app.ementa import theses as split_theses
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

HIGHLIGHT = f"websearch_to_tsquery('{SEARCH_CONFIG}', %(highlight)s)"

# Which words the snippet is cut around. By default the reader's own, which is
# right in a plain search. Arriving from an indicator it is the words the
# classification was read from, because the terms searched for sit where the
# court frames the dispute, not where it answers it: measured over decisions
# that carry a written thesis, 31,5% of snippets landed in "questão em
# discussão" and 2,25% touched the thesis itself.
#
# The sets come from the rules that classify: SCRUM-128 for the outcome,
# read from the dispositive, and SCRUM-166 for the adherence, read from the
# words around the citation. Volume and timeline are not here: their
# classification is a field copied from the source, not a reading of ours,
# so there is no passage to point at.
HIGHLIGHT_TERMS = {
    "resultado": (
        "provimento OR desprovido OR improvido OR provido OR negar OR "
        "rejeitar OR indeferir OR acolher OR conceder OR deferir"
    ),
    "aderencia": (
        "súmula OR tema OR incidência OR aplicar OR inaplicável OR óbice OR "
        "enunciado OR precedente"
    ),
}

SNIPPET = f"""
ts_headline(
    '{SEARCH_CONFIG}', ementa, {HIGHLIGHT},
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

TIEBREAK = "fonte_codigo DESC, identificador_fonte DESC"


def _ordering(*keys: str) -> str:
    """
    An ORDER BY that closes on the unique key of `core.decisao`.

    Relevance and date both tie: hundreds of decisions share a rank, and a
    court decides dozens on the same day. A tie the database is free to break
    however it likes is broken differently for each page, so the same decision
    comes back on two of them while another is never served. Ending on
    `fonte_codigo, identificador_fonte` leaves no tie at all — no two rows carry
    the same pair — and the order becomes the same one every time. An
    identifier alone would not do it: two collections number from 1.

    Built here rather than written out so an ordering added later cannot be the
    one that forgets.
    """
    return "ORDER BY\n    " + ",\n    ".join((*keys, TIEBREAK)) + "\n"


ORDERINGS: dict[Order, str] = {
    "relevance": _ordering(
        f"ts_rank(ementa_busca, {QUERY}) DESC",
        "data_referencia DESC",
    ),
    "date": _ordering("data_referencia DESC"),
}


def _filters_sql(
    tribunals: list[str],
    date_from: date | None,
    date_to: date | None,
    published_from: date | None = None,
    published_to: date | None = None,
    judging_bodies: list[str] | None = None,
    reporting_judges: list[str] | None = None,
    procedural_classes: list[int] | None = None,
    outcomes: list[str] | None = None,
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
    if judging_bodies:
        clauses.append("orgao_julgador = ANY(%(orgao_julgador)s)")
    if reporting_judges:
        clauses.append("relator = ANY(%(relator)s)")
    if procedural_classes:
        clauses.append("classe_cnj = ANY(%(classe_cnj)s)")
    if outcomes:
        clauses.append("resultado = ANY(%(resultado)s)")
    if date_from is not None:
        clauses.append("data_referencia >= %(date_from)s")
    if date_to is not None:
        clauses.append("data_referencia <= %(date_to)s")
    if published_from is not None:
        clauses.append("data_publicacao >= %(published_from)s")
    if published_to is not None:
        clauses.append("data_publicacao <= %(published_to)s")
    return "".join(f" AND {clause}" for clause in clauses)


class Narrowing(NamedTuple):
    """The set a request asks for: one SQL fragment and the values it binds."""

    sql: str
    parameters: dict[str, Any]


def _nonblank_unique_text(values: list[str] | None) -> list[str]:
    """Drop blanks and exact duplicates without changing option identities."""
    return list(dict.fromkeys(value for value in values or [] if value.strip()))


def _narrowing(
    q: str,
    tribunal: list[str] | None,
    date_from: date | None,
    date_to: date | None,
    published_from: date | None,
    published_to: date | None,
    orgao_julgador: list[str] | None = None,
    relator: list[str] | None = None,
    classe_cnj: list[int] | None = None,
    resultado: list[str] | None = None,
) -> Narrowing:
    """
    Read the narrowing once, so nothing can describe a different set.

    The count, the page and the aggregation all build from what this returns.
    A second builder would be a second chance for the total on the screen and
    the rows under it to stop agreeing.
    """
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
    orgaos = _nonblank_unique_text(orgao_julgador)
    relatores = _nonblank_unique_text(relator)
    classes = list(dict.fromkeys(classe_cnj or []))
    outcomes = list(
        dict.fromkeys(value.strip() for value in resultado or [] if value.strip())
    )

    parameters: dict[str, Any] = {"term": q}
    if tribunais:
        parameters["tribunais"] = tribunais
    if orgaos:
        parameters["orgao_julgador"] = orgaos
    if relatores:
        parameters["relator"] = relatores
    if classes:
        parameters["classe_cnj"] = classes
    if outcomes:
        parameters["resultado"] = outcomes
    if date_from is not None:
        parameters["date_from"] = date_from
    if date_to is not None:
        parameters["date_to"] = date_to
    if published_from is not None:
        parameters["published_from"] = published_from
    if published_to is not None:
        parameters["published_to"] = published_to

    return Narrowing(
        _filters_sql(
            tribunais,
            date_from,
            date_to,
            published_from,
            published_to,
            orgaos,
            relatores,
            classes,
            outcomes,
        ),
        parameters,
    )


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
    decisao.url_compartilhada,
    decisao.deliberacao,
    decisao.ementa,
    decisao.tese,
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
    tese,
    deliberacao,
    turma_recursal,
    possui_inteiro_teor,
    url_fonte,
    link_valido,
    url_compartilhada
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

HIGHLIGHT_SQL = f"""
SELECT {FULL_HIGHLIGHT} AS highlighted
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

# LEFT JOIN, not JOIN: a citation the catalogue has no entry for still happened,
# and dropping it here would let the screen show fewer precedents than the court
# named.
PRECEDENTS_SQL = """
SELECT
    dp.corte,
    dp.tipo,
    dp.numero,
    dp.trecho,
    dp.aderencia,
    dp.resolvida,
    dp.corte_declarada,
    p.enunciado,
    p.situacao,
    p.data
FROM core.decisao_precedente AS dp
LEFT JOIN core.precedente AS p
    -- The court has to have been stated for the join to mean anything: both
    -- courts have a Tema 793, and matching on a guessed court answers with
    -- the other one's thesis.
    ON dp.corte_declarada
   AND p.corte = dp.corte AND p.tipo = dp.tipo AND p.numero = dp.numero
WHERE dp.fonte_codigo = %(source)s AND dp.identificador_fonte = %(identifier)s
ORDER BY dp.tipo, dp.numero
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
    source_url_shared: bool = Field(
        default=False,
        description=(
            "Whether this link also reaches another decision in the base. A "
            "court's identifier can name the case rather than the judgement — "
            "the STJ's `num_registro` covers the original acórdão, the embargos "
            "and the agravo alike — and then the link opens a list. True means "
            "the reader has to pick theirs out of it, by the date, the judging "
            "body and the class shown beside it. 0,87% of the collection."
        ),
        examples=[False],
    )
    deliberation: str | None = Field(
        description=(
            "How the panel voted, read from the operative part: `unanime` "
            "when it was of one mind, `maioria` when someone dissented. "
            "`null` when the court records no vote, and also when the "
            "decision holds two appeals voted differently, where there is no "
            "single answer to give. 99,8% of the collection carries one."
        ),
        examples=["unanime"],
    )


class DecisionMatch(DecisionBase):
    thesis: list[str] = Field(
        description=(
            "The thesis the court itself wrote, one entry per numbered item. "
            "Empty when the court did not record one — which is most of the "
            "collection, because the structured ementa is a 2024 standard."
        ),
        examples=[
            [
                (
                    "A palavra da vítima possui especial relevância em crimes "
                    "de violência doméstica, quando coerente e corroborada por "
                    "outros elementos de prova."
                )
            ]
        ],
    )
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
    "source_url_shared": False,
    "deliberation": "unanime",
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
    "thesis": [
        (
            "O prazo de suspensão da execução fiscal corre da ciência da "
            "primeira diligência infrutífera, independentemente de despacho "
            "que a declare."
        )
    ],
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
    "precedents": [
        {
            "court": "STJ",
            "kind": "sumula",
            "number": 106,
            "text": (
                "Proposta a ação no prazo fixado para o seu exercício, a demora "
                "na citação, por motivos inerentes ao mecanismo da Justiça, não "
                "justifica o acolhimento da arguição de prescrição."
            ),
            "status": None,
            "settled_on": None,
            "snippet": (
                "prescricao intercorrente. incidencia da sumula 106/stj. "
                "apelacao desprovida."
            ),
            "adherence": "seguiu",
            "resolved": True,
            "court_stated": True,
        }
    ],
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


class CitedPrecedent(BaseModel):
    court: str = Field(
        description="Which court settled it. `STJ` or `STF`.", examples=["STJ"]
    )
    kind: str = Field(
        description="`sumula` or `tema`, the two the collection carries.",
        examples=["sumula"],
    )
    number: int = Field(description="The precedent's number.", examples=[7])
    text: str | None = Field(
        description=(
            "What the court settled, when the catalogue holds it. `null` means "
            "the decision cited something the catalogue has no entry for — the "
            "citation is still real, and the screen shows it without a text "
            "rather than hiding it. 4% of citations are in this state."
        ),
        examples=[
            "A pretensão de simples reexame de prova não enseja recurso especial."
        ],
    )
    status: str | None = Field(
        default=None,
        description=(
            "Whether it is still in force. Always `null` for a súmula, whose "
            "text is reconstructed from the collection and carries no status: "
            "presenting a cancelled one as current is an error this refuses to "
            "risk."
        ),
        examples=[None],
    )
    settled_on: date | None = Field(
        default=None, description="When it was judged, for temas."
    )
    snippet: str = Field(
        description=(
            "The court's own words around the citation, 220 characters of the "
            "ementa. This is what lets the reader check the label below against "
            "what was actually written."
        ),
        examples=["reexame de provas. incidencia da sumula n. 7 do stj."],
    )
    adherence: str = Field(
        description=(
            "How the decision used it, read from the words around the citation: "
            "`seguiu`, `afastou`, `distinguiu`, `mencionou` or `indeterminado`. "
            "The last is a value, not an absence — a tool that guesses is worse "
            "than one that says it does not know."
        ),
        examples=["seguiu"],
    )
    resolved: bool = Field(
        description="Whether `text` could be filled from the catalogue."
    )
    court_stated: bool = Field(
        description=(
            "Whether the ementa said which court settled it. A tema cited "
            'bare — "Tema 793", with no court — does not identify a '
            "precedent: the STJ and the STF both have one, saying different "
            "things. The citation is kept and the text withheld, because "
            "answering with the wrong court's thesis is worse than answering "
            "nothing. 6.3% of citations are in this state."
        ),
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
    thesis: list[str] = Field(
        description=(
            "The thesis the court itself wrote, one entry per numbered item. "
            "It is the court's own text, not ours: citable as it stands. Empty "
            "when the court did not record one."
        ),
        examples=[
            [
                (
                    "A palavra da vítima possui especial relevância em crimes "
                    "de violência doméstica, quando coerente e corroborada por "
                    "outros elementos de prova."
                )
            ]
        ],
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
    precedents: list[CitedPrecedent] = Field(
        default_factory=list,
        description=(
            "Which súmulas and temas this decision cites, in the order the "
            "numbering gives. Empty for the 72% of the collection that cites "
            "none — an empty list, never an error."
        ),
    )

    model_config = {"json_schema_extra": {"example": STRUCTURED_EXAMPLE}}


class SearchResults(BaseModel):
    total: int = Field(
        description="How many decisions match, beyond the current page.",
        examples=[1847],
    )
    page: int = Field(description="Which page this is, starting at 1.", examples=[1])
    page_size: int = Field(
        description=(
            "How many results per page. The size that was applied, which is "
            "the maximum when a larger one was asked for."
        ),
        examples=[20],
    )
    range_from: int | None = Field(
        description=(
            "Where this page starts within the total, counting from 1, so a "
            "screen can say which slice it is showing. `null` when the page "
            "carries nothing: there is no position to report."
        ),
        examples=[21],
    )
    range_to: int | None = Field(
        description=(
            "Where this page ends within the total, counting from 1 and "
            "including this result. On the last page it is the total itself. "
            "`null` when the page carries nothing."
        ),
        examples=[40],
    )
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
        "source_url_shared": bool(row.get("url_compartilhada")),
        "deliberation": row["deliberacao"],
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
    summary="Search decisions by term and filters",
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
    orgao_julgador: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact judging-body values from `/filters`. Repeat the parameter "
                "for OR within this field; it combines with other filters using "
                "AND. Blank and repeated values are ignored."
            ),
            examples=[["1ª TURMA CÍVEL"], ["1ª TURMA CÍVEL", "CÂMARA CRIMINAL"]],
        ),
    ] = None,
    relator: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact reporting-judge values from `/filters`. Repeat the "
                "parameter for OR within this field; it combines with other "
                "filters using AND. Blank and repeated values are ignored."
            ),
            examples=[["FABRÍCIO FONTOURA BEZERRA"]],
        ),
    ] = None,
    classe_cnj: Annotated[
        list[int] | None,
        Query(
            description=(
                "CNJ class codes from `/filters`. Repeat for OR within this "
                "field; other filters combine using AND. Repeated codes are "
                "ignored. Decisions without a class do not match."
            ),
            examples=[[198], [198, 213]],
        ),
    ] = None,
    resultado: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact outcome values recorded by `/indicators/outcome-share`: "
                "`negado`, `provido`, or `parcialmente_provido`. Repeat for OR "
                "within this field; other filters combine using AND. Blank and "
                "repeated values are ignored. Decisions without an outcome do "
                "not match; unknown values return no matches."
            ),
            examples=[["negado"], ["provido", "parcialmente_provido"]],
        ),
    ] = None,
    highlight: Annotated[
        Literal["resultado", "aderencia"] | None,
        Query(
            description=(
                "Which indicator the reader arrived from, so the snippet is "
                "cut around what produced the classification instead of around "
                "what was typed. `resultado` points at the dispositive, "
                "`aderencia` at the precedent citation. Omitted — a plain "
                "search — the snippet keeps showing where the search terms "
                "are, which is what that reader wants."
            ),
            examples=["aderencia"],
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
    page: Annotated[
        int,
        Query(
            ge=1,
            description=(
                "Which page to read, starting at 1. A page past the last one "
                "answers an empty list with the same total, not an error."
            ),
            examples=[1],
        ),
    ] = 1,
    page_size: Annotated[
        int,
        Query(
            ge=1,
            description=(
                "How many results per page. Anything above "
                f"{settings.search_max_page_size} is served at that maximum "
                "rather than refused, and `page_size` in the answer says which "
                "size was applied."
            ),
            examples=[20],
        ),
    ] = 20,
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

    Paging is stable. Every ordering ends on the decision's unique key, so two
    matches that tie on relevance or on the same judgement day still come back
    in one fixed order — and walking the pages of one search serves every match
    once, with none repeated and none skipped. `range_from` and `range_to` say
    where the page sits inside the total, and are `null` when it carries
    nothing:

        GET /decisions?q=dano+moral&page=2&page_size=20

        {"total": 57, "page": 2, "page_size": 20,
         "range_from": 21, "range_to": 40, "results": [...]}

    A page past the last one is an empty list with the same total, whatever the
    page number, never an error. A `page_size` above the maximum is served at
    the maximum, and the answer says which size was applied.

    `tribunal`, `orgao_julgador`, `relator`, `classe_cnj`, `date_from`, `date_to`,
    `published_from` and `published_to` are optional and narrow the search
    together. Repeated values within one field are ORed; different filters are
    ANDed with the expression and each other. Text values are compared exactly
    as returned by `/filters`, after blank entries are discarded.

    Class values are numeric CNJ codes from `/filters`. Unknown codes return
    no matches; decisions without a class are excluded only when it is filtered.

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
    offset = (page - 1) * page_size

    filters, narrowed = _narrowing(
        q,
        tribunal,
        date_from,
        date_to,
        published_from,
        published_to,
        orgao_julgador,
        relator,
        classe_cnj,
        resultado,
    )
    parameters: dict[str, Any] = {
        **narrowed,
        "highlight": HIGHLIGHT_TERMS.get(highlight or "", q),
        "snippet_options": SNIPPET_OPTIONS,
        "limit": page_size,
        "offset": offset,
    }

    with connection.cursor() as cursor:
        cursor.execute(_count_sql(filters), parameters)
        total = int((cursor.fetchone() or {"total": 0})["total"])

        rows: list[DictRow] = []
        if offset < total:
            cursor.execute(_page_sql(filters, ORDERINGS[order]), parameters)
            rows = cursor.fetchall()

    return SearchResults(
        total=total,
        page=page,
        page_size=page_size,
        range_from=offset + 1 if rows else None,
        range_to=offset + len(rows) if rows else None,
        results=[
            DecisionMatch(
                **_base_fields(row),
                thesis=split_theses(row.get("tese")),
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

        cursor.execute(PRECEDENTS_SQL, parameters)
        cited = [
            CitedPrecedent(
                court=cite["corte"],
                kind=cite["tipo"],
                number=cite["numero"],
                text=cite["enunciado"],
                status=cite["situacao"],
                settled_on=cite["data"],
                snippet=cite["trecho"],
                adherence=cite["aderencia"],
                resolved=cite["resolvida"],
                court_stated=cite["corte_declarada"],
            )
            for cite in cursor.fetchall()
        ]

    return Decision(
        precedents=cited,
        **_base_fields(row),
        class_code=row["classe_cnj"],
        judged_on=row["data_julgamento"],
        published_on=row["data_publicacao"],
        summary=summary,
        outcome=row["decisao_texto"],
        thesis=split_theses(row["tese"]),
        full_text_available=row["possui_inteiro_teor"],
        sections=_sections(row["ementa"]),
    )
