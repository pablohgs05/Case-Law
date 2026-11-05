from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.api import (
    courts,
    decisions,
    doctrine,
    exports,
    filters,
    health,
    indicators,
    session,
    users,
)
from app.config import settings
from app.db import pool
from app.sessions import gate

TAGS = [
    {
        "name": "search",
        "description": "Finding decisions across the collected courts.",
    },
    {
        "name": "indicators",
        "description": "What the collection is: how recent, and how distributed.",
    },
    {
        "name": "doctrine",
        "description": (
            "Legal scholarship that treats what a decision settled. "
            "Enrichment: a decision opens whether this answers or not."
        ),
    },
    {
        "name": "accounts",
        "description": (
            "Signing in, and a manager running their company's access. "
            "Everything else on this API requires an account."
        ),
    },
    {
        "name": "infrastructure",
        "description": "Operational endpoints. Not part of the product surface.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="Case Law API",
    summary="Consolidation and analysis of judicial precedents.",
    description=(
        "Search decisions across Brazilian courts, inspect the reasoning and "
        "measure how a subject is being judged.\n\n"
        "Every result links back to the document on the court's official site: "
        "the source always prevails over any summary this API produces."
    ),
    version="0.1.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
    # Closed by default, on the application rather than on each router: adding
    # a router is not a chance to forget. What may be reached without an
    # account is named in `sessions.PUBLIC_PATHS`, in one readable place.
    dependencies=[Depends(gate)],
    root_path=settings.root_path,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

errors.register(app)

app.include_router(health.router)
app.include_router(decisions.router)
app.include_router(courts.router)
app.include_router(filters.router)
app.include_router(indicators.router)
app.include_router(exports.router)
app.include_router(doctrine.router)
app.include_router(session.router)
app.include_router(users.router)
