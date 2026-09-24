from collections.abc import Iterator
from datetime import date
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.decisions import Decision
from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = needs_database

ENVELOPE = {"total", "page", "page_size", "results"}

MATCH = {
    "source",
    "identifier",
    "court",
    "case_number",
    "judging_body",
    "reporting_judge",
    "decided_on",
    "small_claims",
    "source_url",
    "source_url_reachable",
    "snippet",
}

DETAIL = (MATCH - {"snippet"}) | {
    "class_code",
    "judged_on",
    "published_on",
    "summary",
    "outcome",
    "full_text_available",
    "sections",
}

NULLABLE = {
    "case_number",
    "judging_body",
    "reporting_judge",
    "class_code",
    "judged_on",
    "published_on",
    "outcome",
    "source_url_reachable",
    "sections",
}


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def one_match(client: TestClient) -> dict[str, Any]:
    body = client.get("/decisions", params={"q": "dano moral"}).json()
    return body["results"][0]


def test_the_envelope_carries_exactly_the_agreed_keys(client: TestClient) -> None:
    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert set(body) == ENVELOPE


def test_the_envelope_types_are_what_a_screen_can_page_with(
    client: TestClient,
) -> None:
    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert isinstance(body["total"], int)
    assert isinstance(body["page"], int)
    assert isinstance(body["page_size"], int)
    assert isinstance(body["results"], list)


def test_a_result_carries_exactly_the_agreed_keys(client: TestClient) -> None:
    assert set(one_match(client)) == MATCH


def test_a_result_never_sends_the_whole_ementa(client: TestClient) -> None:
    assert "summary" not in one_match(client)


def test_the_snippet_is_html_the_screen_is_meant_to_render(
    client: TestClient,
) -> None:
    snippet = one_match(client)["snippet"]

    assert isinstance(snippet, str)
    assert "<mark>" in snippet and "</mark>" in snippet


def test_the_result_types_hold(client: TestClient) -> None:
    result = one_match(client)

    assert isinstance(result["source"], str)
    assert isinstance(result["identifier"], str)
    assert isinstance(result["court"], str)
    assert isinstance(result["small_claims"], bool)
    assert isinstance(result["source_url"], str)
    assert result["source_url"].startswith("https://")


def test_dates_are_plain_iso_days_not_timestamps(client: TestClient) -> None:
    result = one_match(client)

    assert date.fromisoformat(result["decided_on"])
    assert "T" not in result["decided_on"]


def test_a_search_with_no_match_keeps_the_same_shape(client: TestClient) -> None:
    body = client.get("/decisions", params={"q": "zzzznaoexiste"}).json()

    assert set(body) == ENVELOPE
    assert body["total"] == 0
    assert body["results"] == []


def test_the_detail_carries_exactly_the_agreed_keys(client: TestClient) -> None:
    identifier = one_match(client)["identifier"]

    body = client.get(f"/decisions/tjdft-jurisdf/{identifier}").json()

    assert set(body) == DETAIL


def test_the_detail_sends_the_ementa_whole(client: TestClient) -> None:
    identifier = one_match(client)["identifier"]

    body = client.get(f"/decisions/tjdft-jurisdf/{identifier}").json()

    assert isinstance(body["summary"], str)
    assert "<mark>" not in body["summary"]


def test_the_detail_highlights_only_when_asked(client: TestClient) -> None:
    identifier = one_match(client)["identifier"]

    body = client.get(
        f"/decisions/tjdft-jurisdf/{identifier}", params={"q": "dano moral"}
    ).json()

    assert "<mark>" in body["summary"]


def test_a_missing_decision_answers_404_with_a_detail(client: TestClient) -> None:
    response = client.get("/decisions/tjdft-jurisdf/000000")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_every_nullable_field_is_declared_nullable(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]

    for model in ("DecisionMatch", "Decision"):
        properties = schema[model]["properties"]
        for field in NULLABLE & set(properties):
            declared = properties[field]
            assert "anyOf" in declared, f"{model}.{field} is not nullable"
            assert {"type": "null"} in declared["anyOf"], f"{model}.{field}"


def test_both_endpoints_are_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/decisions" in paths
    assert "/decisions/{source}/{identifier}" in paths


def test_the_documented_shape_matches_what_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]

    assert set(schema["DecisionMatch"]["properties"]) == MATCH
    assert set(schema["Decision"]["properties"]) == DETAIL
    assert set(schema["SearchResults"]["properties"]) == ENVELOPE


def documented(client: TestClient, path: str) -> dict[str, Any]:
    return client.get("/openapi.json").json()["paths"][path]["get"]["responses"]


def test_both_endpoints_document_how_they_fail(client: TestClient) -> None:
    """
    A caller writes error handling from the spec. An undocumented 503 reads as
    a bug in their code rather than a database that has not been published to.
    """
    search = documented(client, "/decisions")
    detail = documented(client, "/decisions/{source}/{identifier}")

    assert {"400", "503"} <= set(search)
    assert {"400", "404", "503"} <= set(detail)


def test_every_documented_failure_shows_what_the_body_looks_like(
    client: TestClient,
) -> None:
    for path in ("/decisions", "/decisions/{source}/{identifier}"):
        for status, described in documented(client, path).items():
            if status.startswith(("4", "5")) and status != "422":
                body = described["content"]["application/json"]
                assert "example" in body, f"{path} {status} has no example"
                assert isinstance(body["example"]["detail"], str)


def test_the_documented_404_is_the_one_the_endpoint_sends(client: TestClient) -> None:
    """
    Pins the example against reality. Documentation that drifts from the code is
    worse than none: it is trusted.
    """
    described = documented(client, "/decisions/{source}/{identifier}")["404"]
    promised = described["content"]["application/json"]["example"]

    actual = client.get("/decisions/tjdft-jurisdf/000000").json()

    assert actual == promised


def test_the_response_example_carries_every_field_the_schema_has(
    client: TestClient,
) -> None:
    """
    An example that lost a field as the response grew teaches the wrong shape.
    The last field added to this response reached production before anything
    noticed it was missing from the documentation.
    """
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    decision = schemas["Decision"]
    example = decision.get("example")

    assert example is not None, "Decision has no response example"
    assert set(example) == set(decision["properties"])


def test_the_documented_example_would_pass_the_response_model(
    client: TestClient,
) -> None:
    """
    The example is hand written, so nothing stops it carrying a type the API
    never sends. This reads it back through the model that serves the endpoint.
    """
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    example = schemas["Decision"]["example"]

    assert Decision.model_validate(example)
