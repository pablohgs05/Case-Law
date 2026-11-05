"""Printable references from a validated, complete export dataset."""

from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
from math import ceil
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from app.export import ExportDataset
from app.export_indicators import ExportIndicators

# Match decisionFormat.ts, outcomeFormat.ts and ResultsSort.tsx. Contract tests
# guard the wording shared by the Python document and the TypeScript interface.
NOT_INFORMED = "Não informado"
DELIBERATION_LABELS = {
    "unanime": "Unânime",
    "maioria": "Por maioria",
    "nao-informado": NOT_INFORMED,
    "nao-aplicavel": "Não aplicável",
}
OUTCOME_LABELS = {
    "negado": "Negado",
    "provido": "Provido",
    "parcialmente_provido": "Parcialmente provido",
}
ORDER_LABELS = {"relevance": "Relevância", "date": "Mais recentes"}
FILTER_LABELS = {
    "tribunais": "Tribunais",
    "orgao_julgador": "Órgão julgador",
    "relator": "Relator",
    "classe_cnj": "Classe CNJ",
    "resultado": "Resultado",
    "date_from": "Data do julgamento — de",
    "date_to": "Data do julgamento — até",
    "published_from": "Data de publicação — de",
    "published_to": "Data de publicação — até",
}


def display(value: Any) -> str:
    if value is None or not str(value).strip():
        return NOT_INFORMED
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


class ExcerptText(HTMLParser):
    """Strip ts_headline's mark tags before escaping the excerpt as plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def official_reference(row: dict[str, Any]) -> str:
    # Keep the audited url_fonte exactly; never interpolate identifiers into it.
    raw = row.get("url_fonte")
    url = raw.strip() if isinstance(raw, str) else ""
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        valid = valid and not any(c.isspace() or ord(c) < 32 for c in url)
    except ValueError:
        valid = False
    if not valid or row.get("link_valido") is False:
        return '<p class="source">Fonte oficial: Link indisponível no momento.</p>'
    return (
        f'<p class="source">Fonte oficial: <a href="{escape(url, quote=True)}">'
        f'Abrir fonte oficial</a><br><span class="url">{escape(url)}</span></p>'
    )


def decision_entry(index: int, row: dict[str, Any]) -> str:
    vote = display(row.get("deliberacao"))
    outcome = display(row.get("resultado"))
    fields = [
        ("Fonte", row.get("fonte_codigo")),
        ("Identificação da decisão", row.get("identificador_fonte")),
        ("Processo", row.get("processo")),
        ("Tribunal", row.get("tribunal_sigla")),
        ("Órgão julgador", row.get("orgao_julgador")),
        ("Relator", row.get("relator")),
        ("Classe CNJ", row.get("classe_cnj")),
        ("Data do julgamento", row.get("data_julgamento")),
        ("Data de publicação", row.get("data_publicacao")),
        ("Data de referência", row.get("data_referencia")),
        ("Deliberação", DELIBERATION_LABELS.get(vote, vote)),
        ("Resultado", OUTCOME_LABELS.get(outcome, outcome)),
    ]
    metadata = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(display(value))}</dd></div>"
        for label, value in fields
    )
    excerpt = ExcerptText()
    excerpt.feed(row.get("snippet") or "")
    excerpt.close()
    return (
        f'<article class="decision"><h2>{index}. '
        f"{escape(display(row.get('tribunal_sigla')))} — "
        f"{escape(display(row.get('identificador_fonte')))}</h2>"
        f'<dl class="metadata">{metadata}</dl>'
        "<h3>Trecho da ementa</h3>"
        f'<p class="excerpt">{escape(display("".join(excerpt.parts)))}</p>'
        f"{official_reference(row)}</article>"
    )


def horizontal_chart(rows: list[tuple[str, int]], label: str) -> str:
    maximum = max((count for _, count in rows), default=1) or 1
    height = len(rows) * 32 + 30
    bars = "".join(
        f'<text x="155" y="{23 + i * 32}" text-anchor="end">{escape(name)}</text>'
        f'<rect x="165" y="{10 + i * 32}" width="{400 * count / maximum:.2f}" '
        'height="20" rx="2" fill="#6b1730"/>'
        f'<text x="{172 + 400 * count / maximum:.2f}" y="{23 + i * 32}">{count}</text>'
        for i, (name, count) in enumerate(rows)
    )
    return (
        f'<svg class="chart" role="img" aria-label="{escape(label)}" '
        f'viewBox="0 0 640 {height}"><title>{escape(label)}</title>'
        f'<line x1="165" y1="4" x2="165" y2="{height - 15}" stroke="#d9c8cd"/>'
        f'{bars}<text x="165" y="{height - 1}">0</text></svg>'
    )


def period_label(period: date, granularity: str) -> str:
    if granularity == "year":
        return str(period.year)
    if granularity == "quarter":
        return f"{(period.month - 1) // 3 + 1}T/{period.year}"
    return period.strftime("%m/%Y")


def timeline_chart(data: ExportIndicators) -> str:
    periods = data.timeline.periods
    axis_max = max(4, ceil(max(p.decisions for p in periods) / 4) * 4)
    points = [
        (
            48 + (i / (len(periods) - 1) if len(periods) > 1 else 0.5) * 555,
            155 - p.decisions / axis_max * 130,
        )
        for i, p in enumerate(periods)
    ]
    coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    grid = "".join(
        f'<line x1="48" x2="603" y1="{155 - i * 32.5}" y2="{155 - i * 32.5}" stroke="#eadfe0"/>'
        f'<text x="38" y="{159 - i * 32.5}" text-anchor="end">{axis_max * i // 4}</text>'
        for i in range(5)
    )
    stride = max(1, ceil(len(periods) / 6))
    label_indices = list(range(0, len(periods), stride))
    if label_indices[-1] != len(periods) - 1:
        if len(periods) - 1 - label_indices[-1] < stride / 2:
            label_indices.pop()
        label_indices.append(len(periods) - 1)
    labels = "".join(
        f'<text x="{points[i][0]:.2f}" y="181" text-anchor="middle">'
        f"{period_label(p.period, data.timeline.granularity)}</text>"
        for i, p in enumerate(periods)
        if i in label_indices
    )
    dots = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#6b1730"/>' for x, y in points
    )
    return (
        '<svg class="chart" role="img" aria-label="Evolução temporal" viewBox="0 0 640 195">'
        "<title>Evolução temporal</title>"
        + grid
        + f'<polygon points="{points[0][0]:.2f},155 {coordinates} {points[-1][0]:.2f},155" fill="#fff1eb"/>'
        + f'<polyline points="{coordinates}" fill="none" stroke="#6b1730" stroke-width="2"/>'
        + dots
        + labels
        + "</svg>"
    )


def indicator_sections(dataset: ExportDataset) -> str:
    data = dataset.indicators
    total = dataset.total
    classified = data.outcomes.classified
    courts = [(court.abbreviation, court.decisions) for court in data.courts.courts]
    court_text = "; ".join(f"{escape(name)}: {count}" for name, count in courts)
    period_rows = "".join(
        f"<tr><td>{period_label(p.period, data.timeline.granularity)}</td><td>{p.decisions}</td></tr>"
        for p in data.timeline.periods
    )
    outcomes = [
        (OUTCOME_LABELS.get(o.outcome, o.outcome), o.decisions)
        for o in data.outcomes.outcomes
    ]
    outcome_rows = "".join(
        "<tr><td>" + escape(OUTCOME_LABELS.get(o.outcome, o.outcome)) + "</td>"
        f"<td>{o.decisions}</td><td>"
        + (
            f"{o.share:.1f}".replace(".", ",")
            + f"% de {classified} decisões classificadas"
            if classified
            else "Sem base classificada para percentual"
        )
        + "</td></tr>"
        for o in data.outcomes.outcomes
    )
    granularity = {"month": "mensal", "quarter": "trimestral", "year": "anual"}[
        data.timeline.granularity
    ]
    return f"""<section class="indicator"><h2>Volume por tribunal</h2>
<p>Base de cálculo: {total} decisões do recorte.</p>
{horizontal_chart(courts, "Volume por tribunal")}<p>{court_text}.</p></section>
<section class="indicator"><h2>Evolução temporal</h2>
<p>Base de cálculo: {total} decisões do recorte. Granularidade {granularity}.
Os períodos intermediários sem decisões são apresentados com zero.</p>
{timeline_chart(data)}<table><thead><tr><th>Período</th><th>Decisões</th></tr></thead>
<tbody>{period_rows}</tbody></table></section>
<section class="indicator"><h2>Resultado dos recursos</h2>
<p>Base dos percentuais: {classified} decisões classificadas de {total} decisões do recorte.
Sem classificação: {data.outcomes.unclassified} de {total} decisões.</p>
{horizontal_chart(outcomes, "Resultado dos recursos")}
<table><thead><tr><th>Resultado</th><th>Decisões</th><th>Proporção e denominador</th></tr></thead>
<tbody>{outcome_rows}</tbody></table>
<p class="note">Ausência de classificação não equivale a recurso negado.
Os percentuais são arredondados; as contagens são a referência para a soma.</p></section>"""


def methodology_section(dataset: ExportDataset) -> str:
    data = dataset.indicators
    knowledge_text = (
        f"Quanto ao conhecimento do recurso, {data.with_knowledge} de {dataset.total} "
        f"decisões têm classificação e {dataset.total - data.with_knowledge} de "
        f"{dataset.total} não têm. Um registro ausente não permite concluir que o "
        "recurso deixou de ser conhecido."
        if data.with_knowledge is not None
        else "A classificação de conhecimento do recurso não está disponível nesta "
        "publicação; este documento não atribui seu valor por inferência."
    )
    coverage = "".join(
        f"<tr><td>{escape(c.court)}</td><td>{escape(display(c.first))} a {escape(display(c.last))}</td>"
        f"<td>{c.with_class} de {c.documents}</td></tr>"
        for c in data.coverage
    )
    return f"""<section class="methodology"><h2>Metodologia e limites da análise</h2>
<h3>1. Janelas de cobertura diferentes</h3>
<p>A tabela descreve a base publicada dos tribunais abrangidos pelo filtro de
tribunal. Sem esse filtro, inclui todos os tribunais da base, mesmo sem decisões
no recorte. A expressão e os demais filtros não restringem esta tabela de
cobertura. As datas são os
extremos observados, não uma garantia de cobertura contínua. Comparar volumes
sem considerar períodos e fontes diferentes pode levar a conclusões inadequadas.</p>
<table><thead><tr><th>Tribunal</th><th>Cobertura observada na base</th><th>Classe informada na base</th></tr></thead>
<tbody>{coverage}</tbody></table>
<h3>2. Classificações incompletas</h3>
<p>No recorte, {data.outcomes.classified} de {dataset.total} decisões têm resultado
classificado e {data.outcomes.unclassified} de {dataset.total} não têm. Os percentuais
dos resultados usam somente as classificadas, com o denominador ao lado de cada
valor. Ausência de classificação não significa resultado desfavorável.
{knowledge_text}</p>
<h3>3. Classe processual parcial</h3>
<p>No recorte, {data.with_class} de {dataset.total} decisões têm classe CNJ
informada. A disponibilidade varia conforme a fonte e a publicação, como mostra
a tabela da base. Filtrar por classe exclui registros sem esse campo e pode
alterar a participação dos tribunais no recorte. Não se deve estender uma
conclusão desse conjunto a decisões cuja classe não foi informada.</p>
<h3>4. Busca por radical, não por lema</h3>
<p>A busca usa radicalização Snowball em português e desconsidera acentos.
Ela não identifica automaticamente equivalência de significado ou todos os
sinônimos jurídicos. Por exemplo, “moral” e “morais” podem produzir radicais
diferentes e retornar conjuntos distintos. Para repetir a pesquisa, utilize a
expressão literal e os filtros registrados no cabeçalho.</p>
<h3>5. A fonte oficial prevalece</h3>
<p>Este documento é um índice de localização e uma descrição do conjunto
consultado, não substitui a decisão judicial. O conteúdo integral publicado
pelo tribunal, acessível pelo link oficial quando disponível, prevalece sobre
os trechos e as classificações aqui apresentados. Confira a fonte antes de
citar ou interpretar uma decisão. Frequência não representa relevância jurídica,
probabilidade de êxito ou previsão de resultado futuro.</p></section>"""


def render_export_html(
    dataset: ExportDataset, *, generated_at: datetime | None = None
) -> str:
    if dataset.total < 1 or dataset.total != len(dataset.decisions):
        raise ValueError("A document requires a complete, nonempty export dataset.")
    data = dataset.indicators
    if (
        data.courts.total != dataset.total
        or data.timeline.total != dataset.total
        or data.outcomes.total != dataset.total
        or sum(c.decisions for c in data.courts.courts) != dataset.total
        or sum(p.decisions for p in data.timeline.periods) != dataset.total
        or data.outcomes.classified + data.outcomes.unclassified != dataset.total
        or sum(o.decisions for o in data.outcomes.outcomes) != data.outcomes.classified
    ):
        raise ValueError("Export indicators must describe the complete document cut.")
    zone = ZoneInfo("America/Sao_Paulo")
    instant = generated_at if generated_at is not None else datetime.now(zone)
    if instant.utcoffset() is None:
        raise ValueError("Generation time must include a timezone.")
    instant = instant.astimezone(zone)
    timestamp = instant.strftime("%d/%m/%Y %H:%M:%S")
    timestamp += f" · America/Sao_Paulo · {instant.isoformat(timespec='seconds')}"
    filters = []
    for key, label in FILTER_LABELS.items():
        value = dataset.filters.get(key)
        if isinstance(value, list):
            values = [
                OUTCOME_LABELS.get(str(v), v) if key == "resultado" else v
                for v in value
            ]
            rendered = "; ".join(display(v) for v in values) or "Sem restrição"
        else:
            rendered = display(value) if value is not None else "Sem restrição"
        filters.append(
            f"<div><dt>{escape(label)}</dt><dd>{escape(rendered)}</dd></div>"
        )
    count = f"{dataset.total:,}".replace(",", ".")
    entries = "".join(
        decision_entry(i, row) for i, row in enumerate(dataset.decisions, 1)
    )
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Case Law — Referências do recorte</title><style>
@page {{ size:A4; margin:18mm 16mm 20mm; }}
* {{ box-sizing:border-box; }}
body {{ font:12px/1.5 Arial,sans-serif; color:#30242a; }}
h1,h2 {{ font-family:Georgia,serif; color:#421523; }}
h1 {{ font-size:28px; margin:8px 0 16px; }}
h2 {{ font-size:18px; margin:0 0 12px; break-after:avoid; }}
h3 {{ font-size:12px; margin:12px 0 4px; break-after:avoid; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:2px; color:#79636b; }}
.query,.excerpt {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
.query {{ padding:12px; background:#fff1eb; border-left:3px solid #6b1730; }}
.filters,.metadata {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 18px; }}
dl {{ margin:12px 0; }} dl div {{ min-width:0; overflow-wrap:anywhere; }}
dt {{ font-weight:bold; }} dd {{ margin:0; }}
.metadata {{ gap:5px 18px; }}
.metadata dt,.metadata dd {{ display:inline; }}
.metadata dt::after {{ content:': '; }}
.summary {{ border-bottom:1px solid #d9c8cd; padding-bottom:18px; margin-bottom:22px; }}
.decision {{ border-bottom:1px solid #d9c8cd; padding:18px 0; break-inside:avoid; }}
.source {{ font-size:11px; overflow-wrap:anywhere; }}
.url {{ color:#79636b; }} a {{ color:#6b1730; }}
.note {{ font-size:11px; color:#79636b; }}
.indicator {{ break-inside:avoid; padding:16px 0; }}
.chart {{ display:block; width:100%; max-height:260px; margin:12px 0; font:12px Arial; }}
table {{ width:100%; border-collapse:collapse; font-size:11px; }}
th,td {{ padding:5px 8px; text-align:left; border-bottom:1px solid #eadfe0; }}
thead {{ display:table-header-group; }} tr {{ break-inside:avoid; }}
.methodology {{ break-before:page; margin:18px 0; }}
.references {{ break-before:page; }}
</style></head><body><header class="summary">
<p class="eyebrow">Case Law · Exportação do recorte</p>
<h1>Referências da pesquisa</h1>
<h3>Expressão pesquisada</h3><p class="query">{escape(dataset.query)}</p>
<h3>Filtros aplicados</h3><dl class="filters">{"".join(filters)}</dl>
<p><b>Ordenação:</b> {ORDER_LABELS[dataset.order]}<br>
<b>Total de decisões do recorte:</b> {count}<br>
<b>Decisões neste documento:</b> {count}<br>
<b>Gerado em:</b> {escape(timestamp)}</p>
<p class="note">A ordem preserva a pesquisa aplicada. Os trechos de ementa
reproduzem a seleção textual da busca. A data de referência utiliza a data do
julgamento ou, quando ausente na origem, a de publicação; isso não preenche
uma data de julgamento ausente. Consulte a fonte oficial para o conteúdo integral.</p>
</header><main>{indicator_sections(dataset)}{methodology_section(dataset)}
<section class="references"><h2>Decisões e referências</h2>{entries}</section></main>
<p class="note">Frequência não representa relevância jurídica.</p></body></html>"""


def render_export_pdf(
    dataset: ExportDataset, *, generated_at: datetime | None = None
) -> bytes:
    # Validate and build before starting a browser. This function owns no files,
    # connection or pagination state; the collector already fixed the snapshot.
    document = render_export_html(dataset, generated_at=generated_at)
    with (
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        page = browser.new_page(java_script_enabled=False)
        page.route("**/*", lambda route: route.abort())
        page.set_content(document, wait_until="load")
        return page.pdf(
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="font:9px Arial;width:100%;text-align:center;color:#79636b">'
                'Case Law · Página <span class="pageNumber"></span> de '
                '<span class="totalPages"></span></div>'
            ),
        )
