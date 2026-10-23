"""Outcome selections remain repeatable and stable across search pages."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import needs_database
from tests.test_indicator_agreement import indicator_cut, read

pytestmark = needs_database
# Reuse the populated, transactional collection rather than nullable seed data.
__all__ = ["indicator_cut"]


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        (["provido"], 2),
        (["provido", "provido"], 2),
        (["provido", "negado"], 3),
        (["inexistente"], 0),
    ],
)
def test_outcome_restricts_the_existing_cut_once(
    client: TestClient,
    indicator_cut: dict[str, Any],
    outcomes: list[str],
    expected: int,
) -> None:
    original = {**indicator_cut, "tribunal": ["STJ"]}
    assert read(client, "/decisions", original)["total"] == 3
    result = read(client, "/decisions", {**original, "resultado": outcomes})
    assert result["total"] == expected
    assert len(result["results"]) == expected


@pytest.mark.parametrize("order", ["date", "relevance"])
def test_outcome_pagination_has_no_missing_or_repeated_decisions(
    client: TestClient,
    indicator_cut: dict[str, Any],
    order: str,
) -> None:
    cut = {**indicator_cut, "resultado": ["provido"], "order": order}
    complete = read(client, "/decisions", cut)
    pages = [
        read(client, "/decisions", {**cut, "page_size": 1, "page": page})
        for page in (1, 2, 3)
    ]
    assert [page["total"] for page in pages] == [2, 2, 2]
    identifiers = [row["identifier"] for page in pages for row in page["results"]]
    assert identifiers == [row["identifier"] for row in complete["results"]]
    assert set(identifiers) == {"1", "3"}
    assert pages[-1]["results"] == []
