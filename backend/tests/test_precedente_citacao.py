"""
Which precedents an ementa cites, and what happens to the ones the catalogue
does not hold.

The extraction is mirrored from the `citada` CTE in
core_decisao_precedente.sql, so a change there breaks a test here. The shapes
come from the collection rather than from imagination — including the false
positive that passes a code review, where a common noun reads as a citation.
"""

import re
import unicodedata

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import needs_database

SUMULA = re.compile(
    r"sumula\s*(?:n[.oº°]*\s*)?([0-9]{1,4})\s*[/, -]*(?:do\s+)?(stj|stf)"
)
# The number is what separates the precedent from the common noun: without it,
# "relevância do tema" would be a citation of nothing. The court is read from
# the text, as it is for a súmula: both courts have a Tema 793.
TEMA = re.compile(
    r"\btema[s]?\s*(?:n[.oº°]*\s*)?([0-9]{1,4})\b\s*[/, ();-]*(?:d[aeo]\s+)?"
    r"(stf|stj|repercussao geral)?"
)


def _fold(text: str) -> str:
    folded = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"\s+", " ", folded)


def cited(ementa: str) -> set[tuple[str, str, int]]:
    """The rule in core_decisao_precedente.sql, as a set: DISTINCT is the SQL's."""
    text = _fold(ementa)
    found = {
        (court.upper(), "sumula", int(number)) for number, court in SUMULA.findall(text)
    }
    # Aggregated per number, the way the SQL groups: the same ementa names the
    # court in one occurrence and omits it in the next.
    temas: dict[int, str | None] = {}
    for number, court in TEMA.findall(text):
        seen = temas.get(int(number))
        temas[int(number)] = court or seen
    found |= {
        (
            "STF" if court and ("stf" in court or "repercussao" in court) else "STJ",
            "tema",
            number,
        )
        for number, court in temas.items()
    }
    return found


def tema_court_stated(ementa: str) -> dict[int, bool]:
    """Whether the ementa said which court settled each tema it cites."""
    stated: dict[int, bool] = {}
    for number, court in TEMA.findall(_fold(ementa)):
        stated[int(number)] = stated.get(int(number), False) or bool(court)
    return stated


def test_three_precedents_cited_make_three_links() -> None:
    ementa = (
        "PROCESSUAL CIVIL. Incidência da Súmula 7/STJ. Acórdão em consonância "
        "com a Súmula 83 do STJ. Tema 630 do STJ. Agravo desprovido."
    )

    assert cited(ementa) == {
        ("STJ", "sumula", 7),
        ("STJ", "sumula", 83),
        ("STJ", "tema", 630),
    }


def test_the_same_precedent_cited_three_times_makes_one_link() -> None:
    """
    The ementa repeats a súmula in the headnote, in the reasoning and in the
    dispositive. Three rows would inflate every count built on the table, and
    the key would refuse them anyway.
    """
    ementa = (
        "Súmula 7/STJ. Reexame de prova. A súmula 7 do STJ obsta o recurso. "
        "Incidência da Súmula n. 7 do STJ. Agravo desprovido."
    )

    assert cited(ementa) == {("STJ", "sumula", 7)}


@pytest.mark.parametrize(
    "ementa",
    [
        "relevância do tema e da urgência da medida",
        "o tema debatido nos autos não comporta reexame",
        "temas de direito administrativo e tributário",
        "a súmula invocada não se aplica ao caso",
    ],
)
def test_a_common_noun_is_never_read_as_a_citation(ementa: str) -> None:
    """
    The false positive the subtask exists for. "tema" and "súmula" are
    ordinary words in a judgement, and a pattern without the number turns
    thousands of sentences into citations of nothing — which nobody spots in
    review, because the links look plausible one at a time.
    """
    assert cited(ementa) == set()


def test_a_court_the_collection_does_not_carry_is_not_invented() -> None:
    """Only the STJ and the STF settle what this base calls a precedent."""
    assert cited("Súmula 14 do TST e Súmula 331 do TRT") == set()


def test_the_number_is_read_through_the_shapes_the_courts_write() -> None:
    for ementa in (
        "Súmula 284/STF",
        "Súmula n. 284 do STF",
        "Súmula nº 284 STF",
        "súmula 284 - stf",
    ):
        assert cited(ementa) == {("STF", "sumula", 284)}, ementa


pytestmark_db = needs_database


@pytest.mark.usefixtures("db_rolled_back")
class TestResolution:
    """
    What happens to a citation the catalogue has no entry for. It is kept and
    flagged, never dropped: the gap is the measure that says whether widening
    the collection is worth it, and a table that hides it cannot be asked.
    """

    @staticmethod
    def link(
        db: psycopg.Connection[DictRow],
        number: int,
        resolved: bool,
        adherence: str = "seguiu",
    ) -> None:
        db.execute(
            "INSERT INTO core.decisao_precedente"
            " (fonte_codigo, identificador_fonte, corte, tipo, numero, trecho,"
            "  resolvida, aderencia)"
            " VALUES ('stj-teste', 'd1', 'STJ', 'sumula', %s, %s, %s, %s)",
            (number, f"trecho da sumula {number}", resolved, adherence),
        )

    def test_a_citation_outside_the_catalogue_is_kept_and_flagged(
        self, db_rolled_back: psycopg.Connection[DictRow]
    ) -> None:
        self.link(db_rolled_back, 999, resolved=False)

        with db_rolled_back.cursor() as cursor:
            cursor.execute("SELECT * FROM core.decisao_precedente")
            rows = cursor.fetchall()

        assert len(rows) == 1
        assert rows[0]["resolvida"] is False
        assert rows[0]["trecho"]

    def test_every_link_either_resolves_or_says_it_did_not(
        self, db_rolled_back: psycopg.Connection[DictRow]
    ) -> None:
        """
        The audit `citacao_resolvida_com_precedente` in SQL, asked here of the
        rows themselves: no silent middle ground. A catalogue collected halfway
        would leave orphan links flagged as resolved, and the screen would try
        to show a text it does not have.
        """
        db_rolled_back.execute(
            "INSERT INTO core.precedente (corte, tipo, numero, enunciado, origem)"
            " VALUES ('STJ', 'sumula', 7, 'Reexame de prova.', 'reconstruido')"
        )
        self.link(db_rolled_back, 7, resolved=True)
        self.link(db_rolled_back, 999, resolved=False)

        with db_rolled_back.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS wrong"
                " FROM core.decisao_precedente AS dp"
                " LEFT JOIN core.precedente AS p"
                "   ON p.corte = dp.corte AND p.tipo = dp.tipo AND p.numero = dp.numero"
                " WHERE dp.resolvida <> (p.corte IS NOT NULL)"
            )
            answer = cursor.fetchone()

        assert answer is not None
        assert answer["wrong"] == 0

    def test_the_same_pair_cannot_be_written_twice(
        self, db_rolled_back: psycopg.Connection[DictRow]
    ) -> None:
        self.link(db_rolled_back, 7, resolved=False)

        with pytest.raises(psycopg.errors.UniqueViolation):
            self.link(db_rolled_back, 7, resolved=False)


def test_a_tema_of_the_supreme_court_is_not_recorded_as_the_other_one() -> None:
    """
    The defect this test exists for. The court was a constant, so every tema
    was the STJ's — and 11,252 citations showed the thesis of a different
    precedent of the same number. Tema 793 of the STF is about the duty of
    federated entities in health care; Tema 793 of the STJ is about court
    registry records.
    """
    assert cited("Incidência do Tema 793 do STF") == {("STF", "tema", 793)}
    assert cited("nos termos do Tema 793 do STJ") == {("STJ", "tema", 793)}


def test_repercussao_geral_is_the_supreme_court() -> None:
    assert cited("Tema 69 da repercussão geral") == {("STF", "tema", 69)}


def test_a_tema_with_no_court_named_identifies_no_precedent() -> None:
    """
    Both courts have a Tema 793. Reading a bare citation as either one is a
    guess, so the link is kept and the court recorded as not stated — the
    screen then shows the citation without a thesis.
    """
    assert tema_court_stated("conforme o Tema 793, o recurso não prospera") == {
        793: False
    }
    assert tema_court_stated("conforme o Tema 793 do STF") == {793: True}


def test_one_occurrence_naming_the_court_settles_the_whole_citation() -> None:
    """The same ementa names it once and omits it after; one link, not two."""
    ementa = "Tema 793 do STF. Aplicou-se o Tema 793 ao caso."

    assert cited(ementa) == {("STF", "tema", 793)}
    assert tema_court_stated(ementa) == {793: True}
