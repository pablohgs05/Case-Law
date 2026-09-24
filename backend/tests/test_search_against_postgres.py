import psycopg
from psycopg.rows import DictRow

from app.api.decisions import _normalize_highlighted_text
from tests.conftest import needs_database

pytestmark = needs_database

MATCH = """
SELECT COUNT(*) AS total FROM core.decisao
WHERE ementa_busca @@ websearch_to_tsquery('portugues_sem_acento', %(term)s)
"""

SNIPPET = """
SELECT ts_headline(
    'portugues_sem_acento', ementa,
    websearch_to_tsquery('portugues_sem_acento', %(term)s),
    'StartSel=<mark>, StopSel=</mark>, MaxWords=20, MinWords=10'
) AS snippet
FROM core.decisao
WHERE ementa_busca @@ websearch_to_tsquery('portugues_sem_acento', %(term)s)
LIMIT 1
"""


def count(db: psycopg.Connection[DictRow], term: str) -> int:
    with db.cursor() as cursor:
        cursor.execute(MATCH, {"term": term})
        row = cursor.fetchone()
        return int(row["total"]) if row else 0


def test_the_extensions_the_project_depends_on_are_installed(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension")
        installed = {row["extname"] for row in cursor.fetchall()}

    assert {"pg_trgm", "unaccent", "vector"} <= installed


def test_the_search_configuration_exists(db: psycopg.Connection[DictRow]) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT 1 AS found FROM pg_ts_config WHERE cfgname = 'portugues_sem_acento'"
        )
        assert cursor.fetchone() is not None


def test_the_fixture_loads(db: psycopg.Connection[DictRow]) -> None:
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM core.decisao")
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] == 4


def test_searching_without_accents_finds_accented_text(
    db: psycopg.Connection[DictRow],
) -> None:
    assert count(db, "usucapiao") == 1
    assert count(db, "acao") == 1


def test_a_term_matches_every_word(db: psycopg.Connection[DictRow]) -> None:
    assert count(db, "dano moral") == 2


def test_a_quoted_phrase_matches_only_the_sequence(
    db: psycopg.Connection[DictRow],
) -> None:
    assert count(db, '"dano moral"') == 2
    assert count(db, '"moral dano"') == 0


def test_or_widens_the_search(db: psycopg.Connection[DictRow]) -> None:
    assert count(db, "usucapiao") == 1
    assert count(db, "usucapiao OR consumidor") == 2


def test_a_leading_minus_excludes(db: psycopg.Connection[DictRow]) -> None:
    assert count(db, "dano") == 2
    assert count(db, "dano -materiais") == 1


def test_malformed_input_returns_nothing_instead_of_failing(
    db: psycopg.Connection[DictRow],
) -> None:
    assert count(db, '((" & | !') == 0


def test_the_snippet_marks_the_match_and_keeps_the_accents(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        cursor.execute(SNIPPET, {"term": "usucapiao"})
        row = cursor.fetchone()

    assert row is not None
    assert "<mark>Usucapião</mark>" in row["snippet"]


def test_exact_phrase_snippet_groups_the_whole_phrase_in_one_mark(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT ts_headline(
                'portugues_sem_acento', ementa,
                websearch_to_tsquery('portugues_sem_acento', %(term)s),
                'StartSel=<mark>, StopSel=</mark>, MaxWords=20, MinWords=10, MaxFragments=2, FragmentDelimiter='' … '''
            ) AS snippet
            FROM core.decisao
            WHERE ementa_busca @@ websearch_to_tsquery('portugues_sem_acento', %(term)s)
            LIMIT 1
            """,
            {"term": '"dano moral"'},
        )
        row = cursor.fetchone()

    assert row is not None
    normalized = _normalize_highlighted_text(row["snippet"], '"dano moral"')
    assert (
        "<mark>Dano moral</mark>" in normalized
        or "<mark>dano moral</mark>" in normalized.lower()
    )


def test_quoted_phrase_does_not_mark_separate_words_when_they_are_not_adjacent(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            """
            SELECT ts_headline(
                'portugues_sem_acento', ementa,
                websearch_to_tsquery('portugues_sem_acento', %(term)s),
                %(snippet_options)s
            ) AS snippet
            FROM core.decisao
            WHERE ementa_busca @@ websearch_to_tsquery('portugues_sem_acento', %(term)s)
            LIMIT 1
            """,
            {
                "term": '"moral dano"',
                "snippet_options": (
                    "StartSel=<mark>, StopSel=</mark>, "
                    "MaxWords=20, MinWords=10, "
                    "MaxFragments=2, FragmentDelimiter=' … '"
                ),
            },
        )
        row = cursor.fetchone()

    assert row is None


def test_the_text_index_is_used_instead_of_a_sequential_scan(
    db: psycopg.Connection[DictRow],
) -> None:
    with db.cursor() as cursor:
        cursor.execute("SET enable_seqscan = OFF")
        cursor.execute(
            "EXPLAIN " + MATCH.replace("COUNT(*) AS total", "1"),
            {"term": "dano moral"},
        )
        plan = " ".join(str(row["QUERY PLAN"]) for row in cursor.fetchall())

    assert "Bitmap Index Scan" in plan
