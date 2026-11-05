"""
Reading the thesis of a decision the court wrote none for, when asked.

This is the one route in the API that costs money and a quota, so nothing here
happens on its own. A reader opens "Por que esta decisão está aqui", sees that
the court wrote no thesis, and asks. The collection is a million decisions and
the free tier is a few hundred calls a day; the only architecture those two
numbers allow is one where the question comes from a person.

What comes back is never the court's words and never says it is. It is this
tool's reading, with the passage it was drawn from, so the reader can check it
against the ementa on the same screen.
"""

import logging
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app import agente, tese
from app.config import settings
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["thesis"])

NO_DECISION = "Decision not found."
NOT_CONFIGURED = "A leitura automática de tese não está configurada neste ambiente."
UNAVAILABLE = "Não foi possível ler a tese agora. Tente de novo em instantes."

EMENTA_SQL = """
SELECT ementa, tese
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""


Outcome = Literal["read", "none", "unverified"]


class ReadThesis(BaseModel):
    outcome: Outcome = Field(
        description=(
            "What came of the asking. `read`: a thesis was identified and its "
            "passage found in the ementa. `none`: the decision settles no "
            "thesis of substantive law, the ordinary answer for one that "
            "resolves only a procedural question. `unverified`: something came "
            "back that could not be confirmed against the ementa, so it is not "
            "shown. The two refusals are told apart because they mean opposite "
            "things: one is a fact about the decision, the other about the "
            "model."
        ),
    )
    thesis: str | None = Field(
        default=None,
        description=(
            "The thesis this tool read out of the ementa, or null when it "
            "could not identify one. Never the court's own words."
        ),
    )
    passage: str | None = Field(
        default=None,
        description=(
            "The passage of the ementa the thesis was drawn from, found in the "
            "ementa before this response was built. Shown so the reader can "
            "check the reading against the text."
        ),
    )
    model: str | None = Field(
        default=None, description="Which model produced the reading."
    )
    cached: bool = Field(
        description=(
            "True when this reading was already made for this exact ementa and "
            "no model was asked again."
        )
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "outcome": "read",
                "thesis": (
                    "A legitimidade ativa para pleitear dano moral por ricochete "
                    "alcança quem mantém vínculo de proximidade afetiva com o "
                    "ofendido direto."
                ),
                "passage": (
                    "AUTORES LEGITIMADOS COMO VÍTIMAS REFLEXAS. VÍNCULO DE "
                    "PROXIMIDADE AFETIVA COM O OFENDIDO DIRETO."
                ),
                "model": "gemini-3.5-flash",
                "cached": False,
            }
        }
    }


def _decision(
    connection: Connection[DictRow], source: str, identifier: str
) -> dict[str, Any]:
    # A NUL byte cannot be sent to PostgreSQL as text, and both parts arrive
    # from the URL. Refusing it here is the difference between "no such
    # decision" and a stack trace.
    if "\x00" in source or "\x00" in identifier:
        raise HTTPException(status_code=404, detail=NO_DECISION)

    with connection.cursor() as cursor:
        cursor.execute(EMENTA_SQL, {"source": source, "identifier": identifier})
        found = cursor.fetchone()

    if found is None:
        raise HTTPException(status_code=404, detail=NO_DECISION)

    return found


@router.post(
    "/decisions/{source}/{identifier}/thesis",
    summary="Read this decision's thesis",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        409: {
            "model": ErrorResponse,
            "description": (
                "The court wrote a thesis for this decision. Show that one; "
                "asking a model to write another would put words next to a "
                "court's that the court did not write."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Esta decisão já tem tese do tribunal."}
                }
            },
        },
        501: {
            "model": ErrorResponse,
            "description": "No API key is configured in this environment.",
            "content": {"application/json": {"example": {"detail": NOT_CONFIGURED}}},
        },
        503: {
            "model": ErrorResponse,
            "description": (
                "The model could not be reached, or answered nothing usable "
                "twice over. Nothing is stored and the reader may ask again."
            ),
            "content": {"application/json": {"example": {"detail": UNAVAILABLE}}},
        },
    },
)
async def read_thesis(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
) -> ReadThesis:
    """
    Identify the thesis of this decision from its ementa.

    Asked for, never automatic: it spends a quota that the collection's size
    would exhaust in an afternoon if it ran on its own.

    The reading is kept, so the next reader of the same decision pays nothing.
    It is kept against the ementa it was made from, so a decision whose text
    changed in a later publication is read again rather than described by a
    reading of text nobody can see any more.

    A reading the tool could not verify against the ementa is discarded and
    answers `thesis: null`. That is an ordinary outcome, not an error: an
    unverifiable thesis is exactly the thing this route exists not to show.
    """
    decision = _decision(connection, source, identifier)

    if decision["tese"]:
        raise HTTPException(
            status_code=409, detail="Esta decisão já tem tese do tribunal."
        )

    ementa = (decision["ementa"] or "").strip()

    if not ementa:
        return ReadThesis(outcome="unverified", cached=False)

    kept = tese.guardada(
        connection, fonte=source, identificador=identifier, ementa=ementa
    )

    if kept is not None:
        return ReadThesis(
            outcome="read",
            thesis=kept["tese"],
            passage=kept["trecho"],
            model=kept["modelo"],
            cached=True,
        )

    if not settings.google_api_key.strip():
        raise HTTPException(status_code=501, detail=NOT_CONFIGURED)

    try:
        lida = await agente.ler(ementa)
    except agente.SemChave:
        raise HTTPException(status_code=501, detail=NOT_CONFIGURED) from None
    except Exception:
        # Everything, on purpose. Behind this call sit a network, a quota, an
        # authentication and an SDK, and none of their failures is this
        # reader's problem: the answer is the same "try again" either way. The
        # breadth is only safe because nothing is swallowed — the traceback
        # goes to the log, where it is the operator's problem.
        logger.exception("the thesis could not be read for %s/%s", source, identifier)
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None

    # Two refusals that mean opposite things, and the screen says which. An
    # empty answer is a fact about the decision: it settles no thesis, and
    # the instruction asks for exactly that answer. A passage the ementa
    # does not contain is a fact about the model, and the only one worth
    # worrying about.
    #
    # Neither is kept — a refusal cached is a refusal that never improves.
    if lida is not None and not lida.tese.strip() and not lida.trecho.strip():
        return ReadThesis(outcome="none", cached=False)

    if lida is None or not tese.confere(ementa, lida):
        return ReadThesis(outcome="unverified", cached=False)

    stored = tese.guardar(
        connection,
        fonte=source,
        identificador=identifier,
        ementa=ementa,
        lida=lida,
        modelo=settings.gemini_model,
    )

    return ReadThesis(
        outcome="read",
        thesis=stored["tese"],
        passage=stored["trecho"],
        model=stored["modelo"],
        cached=False,
    )
