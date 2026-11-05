"""The PDF must identify the exact cut and preserve its references and order."""

import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from app.api.indicators import (
    CourtVolume,
    OutcomeCount,
    OutcomeShare,
    PeriodVolume,
    VolumeByCourt,
    VolumeByPeriod,
)
from app.export import ExportDataset
from app.export_document import (
    DELIBERATION_LABELS,
    NOT_INFORMED,
    ORDER_LABELS,
    OUTCOME_LABELS,
    official_reference,
    render_export_html,
    render_export_pdf,
)
from app.export_indicators import ExportCourtCoverage, ExportIndicators

GENERATED = datetime(2026, 10, 23, 15, 30, 45, tzinfo=UTC)


def decision(n: int) -> dict[str, Any]:
    return {
        "fonte_codigo": "stj-espelhos",
        "identificador_fonte": f"id-{n:04d}",
        "processo": f"processo-{n:04d}",
        "tribunal_sigla": "STJ",
        "orgao_julgador": "CORTE ESPECIAL",
        "relator": "RELATOR A",
        "classe_cnj": 198,
        "data_julgamento": date(2024, 2, 29),
        "data_publicacao": date(2024, 3, 1),
        "data_referencia": date(2024, 2, 29),
        "deliberacao": "maioria",
        "resultado": "parcialmente_provido",
        "snippet": "CIVIL. Dano <mark>moral</mark> comprovado. Recurso provido em parte.",
        "url_fonte": f"https://example.test/oficial?documento={n}&origem=STJ",
        "link_valido": True,
    }


def dataset(count: int = 1) -> ExportDataset:
    return ExportDataset(
        total=count,
        order="relevance",
        decisions=[decision(n) for n in range(1, count + 1)],
        query='"dano moral" OR "indenização" -tributário',
        filters={
            "tribunais": ["STJ"],
            "orgao_julgador": ["CORTE ESPECIAL"],
            "relator": ["RELATOR A"],
            "classe_cnj": [198],
            "resultado": ["parcialmente_provido"],
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 12, 31),
            "published_from": date(2024, 2, 1),
            "published_to": date(2024, 3, 31),
        },
        indicators=ExportIndicators(
            courts=VolumeByCourt(
                total=count,
                courts=[
                    CourtVolume(
                        abbreviation="STJ",
                        name="Superior Tribunal de Justiça",
                        decisions=count,
                    )
                ]
                if count
                else [],
            ),
            timeline=VolumeByPeriod(
                total=count,
                granularity="month",
                periods=[
                    PeriodVolume(period=date(2024, 2, 1), decisions=count),
                ]
                if count
                else [],
            ),
            outcomes=OutcomeShare(
                total=count,
                classified=count,
                unclassified=0,
                outcomes=[
                    OutcomeCount(
                        outcome="parcialmente_provido",
                        decisions=count,
                        share=100 if count else 0,
                    ),
                    OutcomeCount(outcome="negado", decisions=0, share=0),
                    OutcomeCount(outcome="provido", decisions=0, share=0),
                ]
                if count
                else [],
            ),
            coverage=[
                ExportCourtCoverage(
                    court="STJ",
                    documents=1000,
                    first=date(1989, 2, 19),
                    last=date(2026, 8, 26),
                    with_class=900,
                )
            ],
            with_class=count,
        ),
    )


class DocumentText(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.feed(html)

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def test_header_identifies_literal_expression_every_filter_count_order_and_timezone() -> (
    None
):
    data = dataset()
    text = DocumentText(render_export_html(data, generated_at=GENERATED)).text
    assert data.query in text
    for expected in (
        "Tribunais STJ",
        "Órgão julgador CORTE ESPECIAL",
        "Relator RELATOR A",
        "Classe CNJ 198",
        "Resultado Parcialmente provido",
        "Data do julgamento — de 01/01/2024",
        "Data do julgamento — até 31/12/2024",
        "Data de publicação — de 01/02/2024",
        "Data de publicação — até 31/03/2024",
        "Relevância",
        "Total de decisões do recorte:",
        "Decisões neste documento:",
        "23/10/2026 12:30:45",
        "America/Sao_Paulo",
        "2026-10-23T12:30:45-03:00",
    ):
        assert expected in text


def test_all_absent_metadata_is_explicit_without_inventing_a_judgment_date() -> None:
    data = dataset()
    row = data.decisions[0]
    for key in row:
        row[key] = None
    row["data_referencia"] = date(2024, 3, 1)
    text = DocumentText(render_export_html(data, generated_at=GENERATED)).text
    for label in (
        "Fonte",
        "Identificação da decisão",
        "Processo",
        "Tribunal",
        "Órgão julgador",
        "Relator",
        "Classe CNJ",
        "Data do julgamento",
        "Data de publicação",
        "Deliberação",
        "Resultado",
        "Trecho da ementa",
    ):
        assert f"{label} {NOT_INFORMED}" in text
    assert "Data de referência 01/03/2024" in text
    assert "Fonte oficial: Link indisponível no momento." in text


@pytest.mark.parametrize("vote", [None, "", "  "])
def test_missing_vote_is_not_inferred_from_an_outcome(vote: str | None) -> None:
    data = dataset()
    data.decisions[0]["deliberacao"] = vote
    text = DocumentText(render_export_html(data)).text
    assert "Deliberação Não informado" in text
    assert "Resultado Parcialmente provido" in text


def test_text_is_escaped_and_highlight_tags_do_not_leak_into_the_document() -> None:
    data = dataset()
    data = data._replace(
        query='<script src="https://attack.test/a.js">expressão</script>'
    )
    data.decisions[0]["relator"] = '<img src="https://attack.test/image">'
    html = render_export_html(data, generated_at=GENERATED)
    assert "<script" not in html and "<img" not in html and "<mark>" not in html
    assert data.query in DocumentText(html).text
    assert "Dano moral comprovado" in DocumentText(html).text


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://",
        "http://[bad",
        "https://bad host/",
    ],
)
def test_invalid_or_missing_url_never_becomes_an_invented_link(url: str | None) -> None:
    row = decision(1)
    row["url_fonte"] = url
    result = official_reference(row)
    assert "Link indisponível no momento." in result
    assert "href=" not in result


def test_audited_url_is_kept_exactly_and_broken_links_are_not_followable() -> None:
    row = decision(1)
    row["url_fonte"] = "https://oficial.test/path/123?inteiro=sim&formato=pdf#documento"
    row["identificador_fonte"] = "different-id-must-not-be-interpolated"
    html = official_reference(row)
    assert (
        'href="https://oficial.test/path/123?inteiro=sim&amp;formato=pdf#documento"'
        in html
    )
    assert "different-id" not in html
    row["link_valido"] = False
    assert "href=" not in official_reference(row)


def test_document_labels_match_the_existing_interface() -> None:
    components = Path(__file__).resolve().parents[2] / "frontend/src/components"
    formats = (components / "decisionFormat.ts").read_text(encoding="utf-8")
    outcomes = (components / "outcomeFormat.ts").read_text(encoding="utf-8")
    orders = (components / "ResultsSort.tsx").read_text(encoding="utf-8")
    assert f"'{NOT_INFORMED}'" in formats
    for key, label in DELIBERATION_LABELS.items():
        assert key in formats
        assert f"'{label}'" in formats
    for key, label in OUTCOME_LABELS.items():
        assert f"{key}: '{label}'" in outcomes
    for key, label in ORDER_LABELS.items():
        assert f"value: '{key}', label: '{label}'" in orders


@pytest.mark.parametrize("data", [dataset(0), dataset(2)._replace(total=3)])
def test_refuses_empty_or_incomplete_datasets(data: ExportDataset) -> None:
    with pytest.raises(ValueError, match="complete, nonempty"):
        render_export_pdf(data)


def test_generation_time_cannot_silently_assume_the_machine_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        render_export_html(dataset(), generated_at=GENERATED.replace(tzinfo=None))


def test_one_hundred_decisions_have_pagination_order_and_exact_clickable_references() -> (
    None
):
    data = dataset(100)
    # Deliberately keep a nonnumeric input order. The renderer must not sort again.
    data.decisions.reverse()
    data = data._replace(order="date")
    pdf = render_export_pdf(data, generated_at=GENERATED)
    assert pdf.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    texts = [page.extract_text() for page in reader.pages]
    text = "\n".join(texts)
    assert "Mais recentes" in text
    assert "Total de decisões do recorte: 100" in text
    assert "Decisões neste documento: 100" in text
    assert "Unânime" not in text
    for title in (
        "Volume por tribunal",
        "Evolução temporal",
        "Resultado dos recursos",
        "Metodologia e limites da análise",
    ):
        assert title in text
    for match in re.finditer(r"\d+,\d+%", text):
        following = " ".join(text[match.end() : match.end() + 70].split())
        assert following.startswith(
            f"de {data.indicators.outcomes.classified} decisões classificadas"
        )
    positions = [text.index(row["processo"]) for row in data.decisions]
    assert positions == sorted(positions)
    for index, page_text in enumerate(texts, 1):
        assert f"Página {index} de {len(reader.pages)}" in page_text
    links = [
        annotation.get_object()["/A"]["/URI"]
        for page in reader.pages
        for annotation in page.get("/Annots", [])
        if annotation.get_object().get("/A", {}).get("/S") == "/URI"
    ]
    assert links == [row["url_fonte"] for row in data.decisions]


def test_very_long_excerpt_can_continue_on_multiple_pages_without_losing_its_end() -> (
    None
):
    data = dataset()
    data.decisions[0]["snippet"] = (
        "Fundamentação jurídica extensa. " * 1500
    ) + "FIM-DA-EMENTA"
    pdf = render_export_pdf(data, generated_at=GENERATED)
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "FIM-DA-EMENTA" in text
    assert "Link indisponível" not in text


def test_three_graphs_show_their_bases_and_methodology_covers_every_limit() -> None:
    data = dataset(4)
    html = render_export_html(data, generated_at=GENERATED)
    text = DocumentText(html).text
    for title in ("Volume por tribunal", "Evolução temporal", "Resultado dos recursos"):
        assert f'aria-label="{title}"' in html
        assert title in text
    assert "Base de cálculo: 4 decisões do recorte." in text
    assert (
        "Base dos percentuais: 4 decisões classificadas de 4 decisões do recorte."
        in text
    )
    assert "100,0% de 4 decisões classificadas" in text
    for point in (
        "1. Janelas de cobertura diferentes",
        "2. Classificações incompletas",
        "3. Classe processual parcial",
        "4. Busca por radical, não por lema",
        "5. A fonte oficial prevalece",
    ):
        assert point in text
    assert "19/02/1989 a 26/08/2026" in text
    assert "900 de 1000" in text
    assert "4 de 4 decisões têm classe CNJ" in text
    assert "Snowball" in text
    assert "probabilidade de êxito" in text


def test_no_percentage_is_invented_when_nothing_is_classified() -> None:
    data = dataset(4)
    indicators = data.indicators._replace(
        outcomes=OutcomeShare(
            total=4,
            classified=0,
            unclassified=4,
            outcomes=[
                OutcomeCount(outcome=o, decisions=0, share=0)
                for o in ("negado", "provido", "parcialmente_provido")
            ],
        )
    )
    text = DocumentText(render_export_html(data._replace(indicators=indicators))).text
    assert "Base dos percentuais: 0 decisões classificadas de 4 decisões" in text
    assert "Sem classificação: 4 de 4 decisões" in text
    assert "Sem base classificada para percentual" in text
    assert "0,0%" not in text


def test_classification_percentages_use_classified_decisions_not_all_references() -> (
    None
):
    data = dataset(4)
    indicators = data.indicators._replace(
        outcomes=OutcomeShare(
            total=4,
            classified=3,
            unclassified=1,
            outcomes=[
                OutcomeCount(outcome="negado", decisions=2, share=66.7),
                OutcomeCount(outcome="provido", decisions=1, share=33.3),
                OutcomeCount(outcome="parcialmente_provido", decisions=0, share=0),
            ],
        )
    )
    text = DocumentText(render_export_html(data._replace(indicators=indicators))).text
    assert "66,7% de 3 decisões classificadas" in text
    assert "33,3% de 3 decisões classificadas" in text
    assert "Sem classificação: 1 de 4 decisões" in text
    assert "50,0%" not in text


def test_document_refuses_indicators_from_another_cut() -> None:
    data = dataset(4)
    indicators = data.indicators._replace(
        courts=VolumeByCourt(
            total=100,
            courts=[
                CourtVolume(abbreviation="STJ", name="STJ", decisions=100),
            ],
        ),
    )
    with pytest.raises(ValueError, match="complete document cut"):
        render_export_pdf(data._replace(indicators=indicators))


def test_zero_period_remains_visible_in_the_document() -> None:
    data = dataset(4)
    indicators = data.indicators._replace(
        timeline=VolumeByPeriod(
            total=4,
            granularity="month",
            periods=[
                PeriodVolume(period=date(2024, 1, 1), decisions=3),
                PeriodVolume(period=date(2024, 2, 1), decisions=0),
                PeriodVolume(period=date(2024, 3, 1), decisions=1),
            ],
        )
    )
    text = DocumentText(render_export_html(data._replace(indicators=indicators))).text
    assert "02/2024 0" in text


def test_knowledge_methodology_distinguishes_unavailable_information_from_measured_zero() -> (
    None
):
    data = dataset(4)
    text = DocumentText(render_export_html(data)).text
    assert "conhecimento do recurso não está disponível nesta" in text
    measured = data._replace(indicators=data.indicators._replace(with_knowledge=0))
    text = DocumentText(render_export_html(measured)).text
    assert "conhecimento do recurso, 0 de 4 decisões têm classificação e 4 de 4" in text
    assert "concluir que o recurso deixou de ser conhecido" in text
