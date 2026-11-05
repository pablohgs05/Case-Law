"""
Reading a thesis out of a decision the court did not write one for.

Only 5.8% of the collection carries a thesis the court itself wrote. In the
rest it is dissolved in the ementa, and a reader who wants it has to find it
by reading. This module is the part of that work that does not involve a
model: what is asked for, what is accepted back, and what is kept.

The rule the whole thing turns on is `confere`. A model that writes a thesis
is a model that can write one the decision does not support, and a legal tool
that attributes invented words to a court is worse than a tool that says
nothing. So the model is made to quote: it returns the thesis *and* the
passage of the ementa it drew it from, the passage is looked for in the ementa,
and a reading whose passage is not there is discarded. Nothing unchecked is
ever stored or shown.
"""

import hashlib
import re
import unicodedata
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

# Long enough that a quote cannot be a stock phrase that happens to occur, and
# short enough that an ementa written as one paragraph still yields one.
MIN_TRECHO = 40


class Lida(BaseModel):
    """What the model has to come back with. Prose alone is not accepted."""

    tese: str = Field(
        description=(
            "A tese jurídica que a decisão firma, em uma frase, nas palavras "
            "do acórdão sempre que possível."
        )
    )
    trecho: str = Field(
        description=(
            "O trecho da ementa de onde a tese foi tirada, copiado palavra por "
            "palavra, sem reescrever nada."
        )
    )


INSTRUCAO = """
Você lê acórdãos brasileiros e identifica a tese jurídica que a decisão firma.

A tese é a regra de direito que a decisão aplica e que valeria para outro caso
igual. Não é o resultado do recurso, não é o resumo dos fatos e não é a
descrição do que as partes pediram.

Responda com dois campos:

- `tese`: a regra, em uma frase, usando as palavras do acórdão sempre que
  possível.
- `trecho`: a passagem da ementa de onde você tirou a tese, copiada palavra por
  palavra. Não reescreva, não corrija, não resuma: copie.

O `trecho` é conferido contra o texto original. Se ele não aparecer na ementa
exatamente como você escreveu, a resposta inteira é descartada.

Se a ementa não firmar nenhuma tese — por exemplo quando só decide uma questão
processual, sem afirmar regra de direito material — devolva os dois campos
vazios. Uma resposta vazia é um resultado correto e é melhor do que uma tese
construída para preencher o campo.
"""


def _comparavel(texto: str) -> str:
    """
    The text as it is compared, not as it is shown.

    A model copying from an ementa changes whitespace, keeps or drops an
    accent, and writes a hyphen where the source has a dash. None of that makes
    the quote a different passage, and refusing it would throw away readings
    that are correct. Word order and the words themselves are what matter, and
    those are left alone.
    """
    plano = unicodedata.normalize("NFKD", texto.casefold())
    plano = "".join(letra for letra in plano if not unicodedata.combining(letra))
    return re.sub(r"[^a-z0-9]+", " ", plano).strip()


def digest(ementa: str) -> str:
    """
    Which text a reading was made from.

    The collection is rebuilt from the sources on every publication, and an
    ementa can come back changed. A reading of the old text still sitting in
    the cache would describe a passage that is no longer on screen, so it is
    the digest, not the decision's identifier, that decides whether a stored
    reading still applies.
    """
    return hashlib.sha256(ementa.encode("utf-8")).hexdigest()


def confere(ementa: str, lida: Lida) -> bool:
    """
    Whether this reading may be shown.

    The quote has to be in the ementa and long enough to be a passage rather
    than a common phrase, and there has to be a thesis to go with it. Anything
    else is refused without a second opinion: there is no cheap way to tell a
    good invention from a bad one, and the tool does not need to tell them
    apart to be right about both.
    """
    tese = lida.tese.strip()
    trecho = lida.trecho.strip()

    if not tese or len(trecho) < MIN_TRECHO:
        return False

    return _comparavel(trecho) in _comparavel(ementa)


GUARDADA_SQL = """
SELECT tese, trecho, modelo, criado_em
FROM leitura.tese
WHERE fonte_codigo = %(fonte)s
  AND identificador_fonte = %(identificador)s
  AND ementa_digest = %(digest)s
"""

GUARDAR_SQL = """
INSERT INTO leitura.tese (
    fonte_codigo, identificador_fonte, tese, trecho, modelo, ementa_digest
)
VALUES (
    %(fonte)s, %(identificador)s, %(tese)s, %(trecho)s, %(modelo)s, %(digest)s
)
ON CONFLICT (fonte_codigo, identificador_fonte) DO UPDATE SET
    tese = EXCLUDED.tese,
    trecho = EXCLUDED.trecho,
    modelo = EXCLUDED.modelo,
    ementa_digest = EXCLUDED.ementa_digest,
    criado_em = NOW()
RETURNING tese, trecho, modelo, criado_em
"""


def guardada(
    db: Connection[DictRow], *, fonte: str, identificador: str, ementa: str
) -> dict[str, Any] | None:
    """The reading already made for this exact ementa, if there is one."""
    with db.cursor() as cursor:
        cursor.execute(
            GUARDADA_SQL,
            {
                "fonte": fonte,
                "identificador": identificador,
                "digest": digest(ementa),
            },
        )
        return cursor.fetchone()


def guardar(
    db: Connection[DictRow],
    *,
    fonte: str,
    identificador: str,
    ementa: str,
    lida: Lida,
    modelo: str,
) -> dict[str, Any]:
    """
    Keep a reading that passed `confere`.

    It replaces whatever was there: a row for an ementa that has since changed
    is stale, and two rows for the same decision would leave the screen to pick
    between them.
    """
    with db.cursor() as cursor:
        cursor.execute(
            GUARDAR_SQL,
            {
                "fonte": fonte,
                "identificador": identificador,
                "tese": lida.tese.strip(),
                "trecho": lida.trecho.strip(),
                "modelo": modelo,
                "digest": digest(ementa),
            },
        )
        guardada = cursor.fetchone()

    assert guardada is not None
    return guardada
