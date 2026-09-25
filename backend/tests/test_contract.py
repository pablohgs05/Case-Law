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

pytestmark = [needs_database, pytest.mark.integration]

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
                shown = (
                    [body["example"]]
                    if "example" in body
                    else [named["value"] for named in body.get("examples", {}).values()]
                )
                assert shown, f"{path} {status} has no example"
                for example in shown:
                    assert isinstance(example["detail"], str)


def test_the_documented_404_is_the_one_the_endpoint_sends(client: TestClient) -> None:
    """
    Pins the example against reality. Documentation that drifts from the code is
    worse than none: it is trusted.
    """
    described = documented(client, "/decisions/{source}/{identifier}")["404"]
    promised = described["content"]["application/json"]["example"]

    actual = client.get("/decisions/tjdft-jurisdf/000000").json()

    assert actual == promised


def test_the_documented_inverted_range_is_the_one_the_search_sends(
    client: TestClient,
) -> None:
    described = documented(client, "/decisions")["400"]
    promised = described["content"]["application/json"]["examples"]["inverted range"]

    response = client.get(
        "/decisions",
        params={"q": "dano moral", "date_from": "2026-03-31", "date_to": "2026-03-01"},
    )

    assert response.status_code == 400
    assert response.json() == promised["value"]


def test_the_documented_inverted_publication_period_is_the_one_sent(
    client: TestClient,
) -> None:
    described = documented(client, "/decisions")["400"]
    examples = described["content"]["application/json"]["examples"]
    promised = examples["inverted publication range"]

    response = client.get(
        "/decisions",
        params={
            "q": "dano moral",
            "published_from": "2026-03-31",
            "published_to": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert response.json() == promised["value"]


def test_the_court_list_is_documented_with_its_shape(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/courts"]["get"]
    schemas = spec["components"]["schemas"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Courts"
    }
    assert set(schemas["Courts"]["properties"]) == {"courts"}
    assert set(schemas["Court"]["properties"]) == {"abbreviation", "name"}
    assert set(schemas["Court"]["required"]) == {"abbreviation", "name"}
    assert "with no decision yet, is left out" in operation["description"]


def test_the_court_list_documents_an_empty_answer_and_its_failures(
    client: TestClient,
) -> None:
    responses = documented(client, "/courts")
    shown = responses["200"]["content"]["application/json"]["examples"]
    failures = responses["503"]["content"]["application/json"]["examples"]

    assert {"courts": []} in [named["value"] for named in shown.values()]
    assert failures
    for named in failures.values():
        assert isinstance(named["value"]["detail"], str)


def test_the_documented_court_example_is_what_the_endpoint_serves(
    client: TestClient,
) -> None:
    """The example is hand written. This pins it against the fixture's answer."""
    responses = documented(client, "/courts")
    shown = responses["200"]["content"]["application/json"]["examples"]

    assert client.get("/courts").json() == shown["with decisions"]["value"]


def test_the_search_documents_every_filter(client: TestClient) -> None:
    search = client.get("/openapi.json").json()["paths"]["/decisions"]["get"]
    parameters = {parameter["name"]: parameter for parameter in search["parameters"]}

    filters = ("tribunal", "date_from", "date_to", "published_from", "published_to")
    dates = ("date_from", "date_to", "published_from", "published_to")

    assert set(filters) <= set(parameters)
    assert not any(parameters[name]["required"] for name in filters)
    assert parameters["tribunal"]["schema"]["anyOf"][0]["type"] == "array"
    for name in dates:
        assert parameters[name]["schema"]["anyOf"][0]["format"] == "date", name


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
