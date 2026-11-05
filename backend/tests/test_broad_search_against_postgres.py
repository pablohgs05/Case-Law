import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.decisions import (
    BROAD_DEPTH,
    BROAD_PAGE_SQL,
    BROAD_TERM_SQL,
    ORDERINGS,
    _broad_term,
    _page_sql,
)
from tests.conftest import needs_database

pytestmark = needs_database

"""
Answering a search for one common word from `core.busca_ampla`.

Two things decide whether this story was delivered, and neither is a
stopwatch. The page has to come out of the index without the planner touching
`core.decisao`, because that is what makes 95 seconds into one index read; and
it has to be the *same* page the slow path produces, because the story is
allowed to change the time and nothing else.

A timing assertion would pass on five fixture rows whatever the code did, so
the guard here is the query plan. It fails the day someone drops the index,
reorders the ORDER BY, or adds a column the index does not carry — which is
exactly how this regresses.
"""

# Two of the five fixture decisions carry it, which is what puts it in
# `core.termo_frequente` with the fixture's floor of two.
FREQUENT = "moral"

# Five rows, so the depth the fixture can be paged to is small, but the gate
# being tested is arithmetic and does not care.
PAGE_SIZE = 20


def plan(
    db: psycopg.Connection[DictRow], sql: str, parameters: dict[str, object]
) -> str:
    with db.cursor() as cursor:
        cursor.execute("EXPLAIN " + sql, parameters)
        return "\n".join(str(row["QUERY PLAN"]) for row in cursor.fetchall())


def lexeme_of(db: psycopg.Connection[DictRow], term: str) -> DictRow | None:
    with db.cursor() as cursor:
        return _broad_term(cursor, {"term": term}, "", "relevance", 0, PAGE_SIZE)


def test_a_frequent_term_is_recognised(db: psycopg.Connection[DictRow]) -> None:
    found = lexeme_of(db, FREQUENT)

    assert found is not None
    assert found["lexema"] == "moral"
    assert found["decisoes"] == 2


def test_a_rare_term_is_not_in_the_ranking_table(
    db: psycopg.Connection[DictRow],
) -> None:
    # Usucapião is in one decision only, so it never reached the floor — and a
    # search for it was never slow.
    assert lexeme_of(db, "usucapião") is None


def test_two_words_are_not_the_fast_path(db: psycopg.Connection[DictRow]) -> None:
    """
    `dano moral` matches both decisions that `moral` matches, so the temptation
    is to treat it as the same search. It is not: `ts_rank` of a two-lexeme
    query is not the rank of either lexeme, so the stored order is the wrong
    order. Two words were never the slow case anyway — measured on production,
    `dano moral` matches 29,783 decisions and answers in 0.6s.
    """
    assert lexeme_of(db, "dano moral") is None


def test_a_phrase_is_not_the_fast_path(db: psycopg.Connection[DictRow]) -> None:
    assert lexeme_of(db, '"dano moral"') is None


def test_a_filter_sends_the_search_down_the_slow_path(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    The stored order is the order of the whole collection. Filtering changes
    which decisions are in the set, so a decision stored at position 900 can
    belong on the filtered first page — and the stored order cannot know that.
    """
    with db.cursor() as cursor:
        narrowed = _broad_term(
            cursor,
            {"term": FREQUENT},
            " AND tribunal_sigla = ANY(%(tribunals)s)",
            "relevance",
            0,
            PAGE_SIZE,
        )

    assert narrowed is None


def test_ordering_by_date_sends_the_search_down_the_slow_path(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        assert _broad_term(cursor, {"term": FREQUENT}, "", "date", 0, PAGE_SIZE) is None


def test_a_page_past_the_stored_depth_sends_the_search_down_the_slow_path(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    The table holds 1000 rows per term. A page that would end at 1001 cannot be
    served from it, and answering with what it has would silently drop the rest.
    """
    with db.cursor() as cursor:
        last = _broad_term(
            cursor,
            {"term": FREQUENT},
            "",
            "relevance",
            BROAD_DEPTH - PAGE_SIZE,
            PAGE_SIZE,
        )
        past = _broad_term(
            cursor,
            {"term": FREQUENT},
            "",
            "relevance",
            BROAD_DEPTH - PAGE_SIZE + 1,
            PAGE_SIZE,
        )

    assert last is not None
    assert past is None


def test_the_index_alone_can_answer_the_page(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    The assertion that carries the story: `Index Only Scan`, with `Heap
    Fetches: 0` and no sort. That is what turns 95 seconds into four blocks
    read — the index carries every column the page asks for, already in the
    order it asks for them.

    It needs a table the planner treats the way it treats production. On five
    rows a sequential scan is honestly cheaper than any index, so the fixture
    is given ten thousand rows of one invented term first; they live inside the
    test's transaction and are gone when it ends.

    What this catches: dropping the index, reordering the ORDER BY, or adding a
    column to the page CTE that the index does not carry. Each of those turns
    the plan back into a scan and brings the 95 seconds back, with nothing else
    changing.
    """
    invented = "zzzlexemadeteste"

    with db_rolled_back.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO core.busca_ampla
                (lexema, posicao, rank, data_referencia, fonte_codigo, identificador_fonte)
            SELECT %(lexema)s, n, 1.0 / n, DATE '2026-01-01', 'tjdft-jurisdf', n::TEXT
            FROM GENERATE_SERIES(1, 10000) AS n
            """,
            {"lexema": invented},
        )
        cursor.execute("ANALYZE core.busca_ampla")

        cursor.execute(
            "EXPLAIN (ANALYZE, BUFFERS) "
            + """
            SELECT rank, data_referencia, fonte_codigo, identificador_fonte
            FROM core.busca_ampla
            WHERE lexema = %(lexema)s
            ORDER BY rank DESC, data_referencia DESC,
                     fonte_codigo DESC, identificador_fonte DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"lexema": invented, "limit": PAGE_SIZE, "offset": 0},
        )
        shape = "\n".join(str(row["QUERY PLAN"]) for row in cursor.fetchall())

    assert "Index Only Scan" in shape
    assert "Sort" not in shape
    assert "Seq Scan" not in shape

    # The number the story is about. Ten thousand rows carry the term and the
    # page touches a handful of blocks, because the depth of the term stopped
    # being the cost of reading it. On production the same shape read four.
    # Everything below "Planning:" is the planner reading the catalog, which is
    # not what this measures.
    executed = shape.split("Planning:")[0]
    read = max(
        int(part.split("=")[1])
        for line in executed.splitlines()
        if "Buffers: shared" in line
        for part in line.split()
        if part.startswith(("hit=", "read="))
    )
    assert read < 50, shape


def test_the_fast_page_is_the_same_page_the_slow_path_gives(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Position by position, not as a set.

    On production this was run over the first 100 results for `recurso` —
    765,840 matches, 95.3s the old way — and came back with zero divergent
    positions. Here it runs over whatever the fixture holds, so that the day
    the stored rank stops being the live rank, a test says so.
    """
    parameters = {
        "term": FREQUENT,
        "highlight": FREQUENT,
        "snippet_options": "StartSel=<mark>, StopSel=</mark>",
        "limit": PAGE_SIZE,
        "offset": 0,
    }

    with db.cursor() as cursor:
        cursor.execute(_page_sql("", ORDERINGS["relevance"]), parameters)
        slow = [
            (row["fonte_codigo"], row["identificador_fonte"])
            for row in cursor.fetchall()
        ]

        cursor.execute(BROAD_PAGE_SQL, {**parameters, "lexema": "moral"})
        fast = [
            (row["fonte_codigo"], row["identificador_fonte"])
            for row in cursor.fetchall()
        ]

    assert fast == slow
    assert fast != []


def test_the_stored_rank_is_the_live_rank(db: psycopg.Connection[DictRow]) -> None:
    """
    The error this catches does not break anything visible: a ranking built
    through the wrong search configuration is still a ranking, still fast, and
    still wrong. The audit `busca_ampla_na_mesma_ordem` guards the base; this
    guards the fixture the other tests trust.
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS divergencias
            FROM core.busca_ampla AS b
            JOIN core.decisao AS d
              ON d.fonte_codigo = b.fonte_codigo
             AND d.identificador_fonte = b.identificador_fonte
            WHERE b.rank IS DISTINCT FROM
                  TS_RANK(d.ementa_busca, QUOTE_LITERAL(b.lexema)::TSQUERY)::REAL
            """
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["divergencias"] == 0


def test_the_lexeme_is_never_parsed_a_second_time(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Why `core_busca_ampla.sql` casts a literal to `tsquery` instead of calling
    `to_tsquery`.

    A lexeme has already been through the parser and the stemmer by the time it
    is in the tsvector. Sending it back produces something else for 225 of the
    1,183 frequent terms on production: 214 lose another suffix — `acorda`,
    323,845 decisions, becomes `acord` — and 11 carry a hyphen, so
    `fatico-probatori`, 89,404 decisions, is read as a three-word phrase.

    Either way the term stops matching and the table gets no rows for it, which
    is how the defect was found: the first build came out 11,000 rows short, one
    thousand for each hyphenated term. A search for "acórdão" would have
    answered an empty first page.

    The five fixture decisions cannot show this end to end — their lexemes are
    all stable — so the fact itself is asserted here, and
    `busca_ampla_cobre_todo_termo_frequente` is what catches it in the base.
    """
    lido = """
        SELECT QUOTE_LITERAL(%(lexema)s)::TSQUERY::text AS literal,
               TO_TSQUERY('simple', QUOTE_LITERAL(%(lexema)s))::text AS analisado
    """

    with db.cursor() as cursor:
        cursor.execute(lido, {"lexema": "acorda"})
        radical = cursor.fetchone()
        cursor.execute(lido, {"lexema": "fatico-probatori"})
        hifen = cursor.fetchone()
        cursor.execute(
            """
            SELECT TO_TSQUERY('portugues_sem_acento', QUOTE_LITERAL(%(lexema)s))::text
                       AS radicalizado_de_novo
            """,
            {"lexema": "acorda"},
        )
        outra_vez = cursor.fetchone()

    assert radical is not None and hifen is not None and outra_vez is not None

    # The literal is the lexeme, whatever is in it.
    assert radical["literal"] == "'acorda'"
    assert hifen["literal"] == "'fatico-probatori'"

    # The parser takes the hyphen apart even under `simple`, which has no
    # stemmer at all: splitting is the parser's doing, not the dictionary's.
    assert hifen["analisado"] == "'fatico-probatori' <-> 'fatico' <-> 'probatori'"

    # And the search configuration stems what is already a stem.
    assert outra_vez["radicalizado_de_novo"] == "'acord'"


def test_a_compound_lexeme_is_never_stored(db: psycopg.Connection[DictRow]) -> None:
    """
    `core.termo_frequente` only holds lexemes a typed word can produce on its
    own. A hyphenated one cannot: the parser reads "fático-probatório" as a
    five-node phrase, so `numnode` is never 1 and the fast path never fires for
    it. Checked on the base, the stored order for `fatico-probatori` differs
    from the search's order in 96 of the first 100 positions — one is the
    ranking of a lexeme, the other of a three-word phrase.

    So the rows would be unreachable today and wrong the day somebody loosens
    the gate. Eleven of the 1,183 terms above the floor are dropped for this.
    Their searches stay slow: 89,404 decisions, about 11s on production.
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS compostos
            FROM core.termo_frequente
            WHERE NUMNODE(TO_TSQUERY('simple', QUOTE_LITERAL(lexema))) <> 1
            """
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["compostos"] == 0


def test_every_frequent_term_has_a_page(db: psycopg.Connection[DictRow]) -> None:
    """
    A term above the floor with no stored page is a search that still takes 95
    seconds, and nothing on the screen would say so: the answer is the same,
    it just waits. Mirrors the pipeline audit of the same name, over whatever
    the fixture built.
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS descobertos
            FROM core.termo_frequente AS t
            LEFT JOIN (
              SELECT lexema, COUNT(*) AS linhas FROM core.busca_ampla GROUP BY lexema
            ) AS b ON b.lexema = t.lexema
            WHERE COALESCE(b.linhas, 0) <> LEAST(t.decisoes, %(profundidade)s)
            """,
            {"profundidade": BROAD_DEPTH},
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["descobertos"] == 0


def test_the_total_is_the_counted_total_and_not_an_estimate(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    The count is the one expense the fast path does not pay either: it was
    counted once when the base was built. It has to be the same number the
    database would answer today, or the screen says 765,840 while the pages add
    up to something else.
    """
    with db.cursor() as cursor:
        cursor.execute(BROAD_TERM_SQL, {"term": FREQUENT})
        stored = cursor.fetchone()
        cursor.execute(
            """
            SELECT COUNT(*) AS total FROM core.decisao
            WHERE ementa_busca @@ websearch_to_tsquery('portugues_sem_acento', %(term)s)
            """,
            {"term": FREQUENT},
        )
        counted = cursor.fetchone()

    assert stored is not None
    assert counted is not None
    assert stored["decisoes"] == counted["total"]

    answered = client.get("/decisions", params={"q": FREQUENT})

    assert answered.status_code == 200
    assert answered.json()["total"] == counted["total"]


def test_the_endpoint_answers_the_same_results_either_way(client: TestClient) -> None:
    """
    End to end, through the route the browser calls. Relevance takes the fast
    path and date does not, so the two orders are different on purpose — what
    has to match is the set of decisions found.
    """
    by_relevance = client.get(
        "/decisions", params={"q": FREQUENT, "order": "relevance"}
    )
    by_date = client.get("/decisions", params={"q": FREQUENT, "order": "date"})

    assert by_relevance.status_code == 200
    assert by_date.status_code == 200

    found = {
        (result["source"], result["identifier"])
        for result in by_relevance.json()["results"]
    }
    assert found == {
        (result["source"], result["identifier"]) for result in by_date.json()["results"]
    }
    assert by_relevance.json()["total"] == by_date.json()["total"]
