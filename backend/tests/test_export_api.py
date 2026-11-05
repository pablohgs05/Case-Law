from collections.abc import Iterator
from datetime import date
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api import exports
from app.db import get_connection
from app.export import ExportDataset, ExportRefused
from app.main import app
from tests.test_export_document import dataset


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: object()

    def collect(_: Any, **params: Any) -> ExportDataset:
        assert "page" not in params and "page_size" not in params
        return dataset(12)._replace(query=params["q"], order=params["order"])

    monkeypatch.setattr(exports, "collect_export", collect)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_options_reports_unlimited_exports(client: TestClient) -> None:
    response = client.get("/exports/options")
    assert response.status_code == 200
    assert response.json() == {"max_decisions": None}


def test_download_is_complete_named_and_contains_all_references(
    client: TestClient,
) -> None:
    response = client.post("/exports/pdf", json={"q": '"dano moral"', "order": "date"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert int(response.headers["content-length"]) == len(response.content)
    name = response.headers["content-disposition"]
    assert name.startswith('attachment; filename="case-law-recorte-dano-moral-')
    assert name.endswith('.pdf"')
    assert "no-store" in response.headers["cache-control"]
    reader = PdfReader(BytesIO(response.content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Decisões neste documento: 12" in text
    assert "Mais recentes" in text
    for n in range(1, 13):
        assert f"processo-{n:04d}" in text


def test_empty_cut_has_no_document_headers_or_renderer_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise ExportRefused()

    def must_not_render(*_: Any, **__: Any) -> Any:
        pytest.fail("a refused cut must never reach the renderer")

    monkeypatch.setattr(exports, "collect_export", refuse)
    monkeypatch.setattr(exports, "render_export_pdf", must_not_render)
    response = client.post("/exports/pdf", json={"q": "dano moral"})
    assert response.status_code == 409
    assert response.json()["code"] == "empty"
    assert response.json()["total"] == 0
    assert "content-disposition" not in response.headers
    assert response.headers["content-type"] == "application/json"


def test_failure_during_rendering_never_sends_a_partial_pdf(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: Any, **__: Any) -> bytes:
        raise RuntimeError("renderer stopped after producing some internal pages")

    monkeypatch.setattr(exports, "render_export_pdf", fail)
    response = client.post("/exports/pdf", json={"q": "dano moral"})
    assert response.status_code == 503
    assert "content-disposition" not in response.headers
    assert response.json() == {
        "detail": "Não foi possível gerar o PDF. Tente novamente."
    }
    assert not response.content.startswith(b"%PDF")


def test_request_preserves_all_applied_filters_and_never_accepts_pagination(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def collect(_: Any, **params: Any) -> ExportDataset:
        captured.update(params)
        return dataset()._replace(query=params["q"])

    monkeypatch.setattr(exports, "collect_export", collect)
    body: dict[str, Any] = {
        "q": '"dano moral" -tributário',
        "tribunal": ["STJ", "TJDFT"],
        "orgao_julgador": ["CORTE ESPECIAL"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["provido"],
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "published_from": "2024-02-01",
        "published_to": "2024-03-31",
        "order": "date",
    }
    assert client.post("/exports/pdf", json=body).status_code == 200
    for key, value in body.items():
        assert captured[key] == (
            date.fromisoformat(value)
            if key
            in {
                "date_from",
                "date_to",
                "published_from",
                "published_to",
            }
            else value
        )
    assert client.post("/exports/pdf", json={**body, "page": 2}).status_code == 422
    assert client.post("/exports/pdf", json={**body, "page_size": 6}).status_code == 422


def test_filename_is_safe_and_distinguishes_filters_even_with_the_same_expression() -> (
    None
):
    from datetime import UTC, datetime

    instant = datetime(2026, 10, 23, 12, tzinfo=UTC)
    first = exports.ExportRequest(q='dano / moral\r\n"<>', tribunal=["STJ"])
    second = first.model_copy(update={"tribunal": ["TJDFT"]})
    name = exports.export_filename(first, instant)
    assert "2026-10-23" in name
    assert not any(c in name for c in '/\\\r\n"<>')
    assert name != exports.export_filename(second, instant)


def test_cross_origin_download_exposes_the_filename(client: TestClient) -> None:
    response = client.post(
        "/exports/pdf",
        json={"q": "dano moral"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert "Content-Disposition" in response.headers["access-control-expose-headers"]
