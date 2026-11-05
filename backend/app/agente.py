"""
The agent that reads an ementa, built with the Google Agent Development Kit.

One agent, one turn, one structured answer. The ADK is an agent framework and
this is not an agent problem — there is no tool to call and nothing to decide
between turns — so nothing here uses its loop. What it is used for is the part
it does well: declaring the model, the instruction and the answer's shape in
one place, and keeping the call to Gemini out of our code.

Everything that decides whether a reading is good lives in `tese.py`, with no
import of this module. That is on purpose: the judgement has to be testable
without a key, without a network, and without the framework.
"""

import json
import logging
from typing import Any

from app.config import settings
from app.tese import INSTRUCAO, Lida

logger = logging.getLogger(__name__)

APP = "case-law"
AGENTE = "leitor_de_tese"


class SemChave(RuntimeError):
    """No API key configured, so no reading can be made."""


def montar() -> Any:
    # Imported here, not at module load: the API has to start and serve every
    # other route on a machine where the ADK is not installed or no key is set.
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.genai import types

    return LlmAgent(
        name=AGENTE,
        # The key goes to the client, not through `GOOGLE_API_KEY` in the
        # environment. Naming the model as a bare string makes the SDK look
        # there instead, which fails on a server that keeps its secrets in a
        # file — and fails with "No API key was provided" for a key that is
        # perfectly well configured.
        model=Gemini(
            model=settings.gemini_model,
            client_kwargs={"api_key": settings.google_api_key.strip()},
            # The free tier answers "high demand" often enough that one
            # attempt is not a fair test of whether a thesis can be read.
            # Four tries over a few seconds, and the reader waits instead
            # of being told to come back.
            retry_options=types.HttpRetryOptions(
                attempts=4,
                initial_delay=1.0,
                max_delay=8.0,
                http_status_codes=[429, 500, 502, 503, 504],
            ),
        ),
        description="Identifica a tese jurídica firmada por um acórdão.",
        instruction=INSTRUCAO,
        output_schema=Lida,
        output_key="lida",
    )


def _resposta(eventos: list[Any]) -> str | None:
    """The last text the agent produced, or None if it produced none."""
    for evento in reversed(eventos):
        conteudo = getattr(evento, "content", None)
        partes = getattr(conteudo, "parts", None) or []
        texto = "".join(getattr(parte, "text", "") or "" for parte in partes)

        if texto.strip():
            return texto

    return None


async def ler(ementa: str) -> Lida | None:
    """
    Ask the model for the thesis of this ementa.

    Returns None when the model answers with nothing usable — an empty answer,
    something that is not the shape we asked for, or a refusal. None is an
    ordinary outcome here, not a failure: the caller shows nothing, and the
    reader is told the tool could not identify a thesis.

    A reading that comes back still has to pass `tese.confere` before anyone
    sees it. This function does not check; it only asks.
    """
    if not settings.google_api_key.strip():
        raise SemChave(
            "GOOGLE_API_KEY is not set, so the thesis cannot be read. Get a key "
            "from Google AI Studio and set it on the server."
        )

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    executor = InMemoryRunner(montar(), app_name=APP)

    try:
        sessao = await executor.session_service.create_session(
            app_name=APP, user_id=AGENTE
        )
        eventos = [
            evento
            async for evento in executor.run_async(
                user_id=AGENTE,
                session_id=sessao.id,
                new_message=types.Content(role="user", parts=[types.Part(text=ementa)]),
            )
        ]
    finally:
        await executor.close()

    texto = _resposta(eventos)

    if not texto:
        return None

    try:
        return Lida.model_validate(json.loads(texto))
    except (json.JSONDecodeError, ValueError):
        # The schema was declared, so this means the model ignored it. Worth a
        # line in the log and nothing more: the reader gets the same "could not
        # identify" as for an empty answer.
        logger.warning("the agent answered outside the schema it was given")
        return None
