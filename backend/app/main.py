from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errors
from app.api import courts, decisions, health, indicators
from app.config import settings
from app.db import pool

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
    root_path=settings.root_path,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

errors.register(app)

app.include_router(health.router)
app.include_router(decisions.router)
app.include_router(courts.router)
app.include_router(indicators.router)
