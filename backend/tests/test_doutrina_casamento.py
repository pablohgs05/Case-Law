"""
The matching rule, run as the pipeline runs it.

The threshold is the promise this story makes to a reader: a suggestion about
another subject costs more than no suggestion at all. It lives in a SQLMesh
model rather than in Python, so a test that re-states it here would pass
whatever the model did. These read the model's own SQL off disk and execute
it, the way `test_courts` reads the real seed CSV — remove a clause from the
model and the test that guards it fails.
"""

from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

MODEL = (
    Path(__file__).resolve().parents[2]
    / "pipeline"
    / "transformations"
    / "models"
    / "core_decisao_doutrina.sql"
)

WORK = "oai:bdjur.stj.jus.br:2011/98958"
TITLE = "Litigância de má-fé no processo civil brasileiro"

# A thesis that shares the title's distinctive words, and says them together.
THESIS = (
    "1. A multa por litigância de má-fé exige prévia oitiva da parte, sendo "
    "vedada decisão surpresa."
)


def matching_sql() -> str:
    """
    The model's body, without the SQLMesh wrapper. The MODEL block and the
    index statements are the engine's; the SELECT between them is the rule.
    """
    text = MODEL.read_text(encoding="utf-8")
    body = text.split("*/", 1)[1].split("JINJA_STATEMENT_BEGIN", 1)[0]
    return body.strip().rstrip(";").strip()


def shelve(db: psycopg.Connection[DictRow], title: str = TITLE) -> None:
    db.execute(
        "INSERT INTO core.doutrina ("
        "  repositorio, identificador_oai, titulo, url_fonte"
        ") VALUES ('bdjur', %s, %s, 'https://bdjur.stj.jus.br/handle/2011/98958')",
        (WORK, title),
    )


def weigh(
    db: psycopg.Connection[DictRow], weight: float, text: str = TITLE
) -> list[str]:
    """
    The work's vocabulary, weighed. Derived from the real tsvector rather than
    written by hand, so the stems are whatever this database's configuration
    produces and the test does not depend on guessing them.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core.doutrina_termo ("
            "  repositorio, identificador_oai, termo, decisoes, peso"
            ") SELECT 'bdjur', %(work)s, t.lexeme, 1, %(weight)s"
            " FROM UNNEST(TO_TSVECTOR('portugues_sem_acento', %(text)s)) AS t"
            " WHERE LENGTH(t.lexeme) >= 4"
            " RETURNING termo",
            {"work": WORK, "weight": weight, "text": text},
        )
        return [row["termo"] for row in cursor.fetchall()]


def decide_with_thesis(
    db: psycopg.Connection[DictRow], identifier: str, thesis: str | None
) -> None:
    decide(db, "STJ", identifier)
    db.execute(
        "UPDATE core.decisao SET tese = %s WHERE identificador_fonte = %s",
        (thesis, identifier),
    )


def suggestions(db: psycopg.Connection[DictRow]) -> list[DictRow]:
    with db.cursor() as cursor:
        cursor.execute(matching_sql())
        return cursor.fetchall()


@pytest.fixture
def collection(db_rolled_back: psycopg.Connection[DictRow]) -> Any:
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    shelve(db_rolled_back)
    return db_rolled_back


def test_uma_tese_casa_com_a_obra_do_mesmo_assunto(
    collection: psycopg.Connection[DictRow],
) -> None:
    """
    O caso que a história existe para servir: tese sobre litigância de má-fé,
    obra sobre litigância de má-fé.
    """
    decide_with_thesis(collection, "com-tese", THESIS)
    weigh(collection, 5.0)

    linhas = suggestions(collection)

    assert len(linhas) == 1
    assert linhas[0]["identificador_oai"] == WORK
    assert linhas[0]["nota"] >= 9.0


def test_sem_termo_proprio_do_assunto_nada_e_sugerido(
    collection: psycopg.Connection[DictRow],
) -> None:
    """
    O teste que o card chama de decisivo. Quatro termos em comum, juntos na
    tese, somando 16 — passa na contagem, na nota e na proximidade. Só o piso
    de 4,5 o segura, e é o que derruba o erro mais convincente: acúmulo de
    palavra comum sem nenhuma própria do assunto.
    """
    decide_with_thesis(
        collection,
        "com-tese",
        "1. A litigância de má-fé no processo civil exige prévia oitiva.",
    )
    termos = weigh(collection, 4.0)

    assert len(termos) >= 4, termos
    assert suggestions(collection) == []


def test_um_termo_so_nao_sugere(collection: psycopg.Connection[DictRow]) -> None:
    """
    Uma palavra em comum é coincidência, por mais rara que seja.

    Duas partes do modelo garantem isso, e a redundância é deliberada: o
    `HAVING COUNT(*) >= 2` diz a regra, e o cálculo de proximidade precisa de
    um par para existir. Tirar só o HAVING não muda esta resposta — foi
    verificado —, então este teste responde pelo comportamento, não por
    aquela linha.
    """
    decide_with_thesis(collection, "com-tese", "A litigância do réu.")
    weigh(collection, 9.9, text="Litigância")

    assert suggestions(collection) == []


def test_nota_baixa_nao_sugere(collection: psycopg.Connection[DictRow]) -> None:
    """
    Dois termos, um deles acima do piso, somando menos de 9. Só o piso da nota
    segura esta sugestão: tirá-lo do modelo a faz aparecer.
    """
    decide_with_thesis(collection, "com-tese", THESIS)
    forte = weigh(collection, 4.6, text="Litigância")
    fraco = weigh(collection, 4.0, text="oitiva")

    assert len(forte) == 1 and len(fraco) == 1, (forte, fraco)
    assert suggestions(collection) == []


def test_termos_espalhados_na_tese_nao_sugerem(
    collection: psycopg.Connection[DictRow],
) -> None:
    """
    A quarta condição: os termos têm de formar expressão. Aqui eles aparecem
    na mesma tese, com peso de sobra, e a vinte palavras de distância.
    """
    espalhada = (
        "1. A litigância temerária foi alegada pela parte recorrente em sede "
        "de contrarrazões, sem que o juízo de origem tenha se manifestado "
        "sobre o ponto ao julgar o feito, o que atrai a exigência de prévia "
        "oitiva antes de reconhecer a má-fé."
    )
    decide_with_thesis(collection, "com-tese", espalhada)
    weigh(collection, 6.0, text="Litigância má-fé")

    assert suggestions(collection) == []


def test_decisao_sem_tese_nao_quebra(
    collection: psycopg.Connection[DictRow],
) -> None:
    """
    94,2% da coleção não tem tese extraída. Se isso fosse erro em vez de
    ausência, o casamento quebraria na carga.
    """
    decide_with_thesis(collection, "sem-tese", None)
    weigh(collection, 9.0)

    assert suggestions(collection) == []


def test_toda_sugestao_traz_o_motivo_preenchido(
    collection: psycopg.Connection[DictRow],
) -> None:
    """
    Sem o motivo a sugestão não responde por si, e o leitor tem de abrir o
    artigo para descobrir se tem a ver — que é o custo que ela existe para
    poupar.
    """
    decide_with_thesis(collection, "com-tese", THESIS)
    weigh(collection, 5.0)

    for linha in suggestions(collection):
        assert linha["casou_em"], linha
        assert len(linha["casou_em"]) == linha["termos"]
        assert linha["termo_mais_forte"] >= 4.5
