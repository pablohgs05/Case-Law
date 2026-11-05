"""
Legal scholarship from the BDJur, the STJ's digital library.

OAI-PMH, the protocol repositories are harvested with: paging by
`resumptionToken`, incremental collection by `from`/`until`, and metadata in
Dublin Core. Only the sets the library itself declares open access are read —
`col_2011_8`, Artigos de Acesso Aberto. The restricted collection is never
touched. Metadata and the link back, never the work: open to read is not open
to redistribute.

**The endpoint refuses automated access.** Since 2026-10-24 the host answers
HTTP 403 to anything that is not a browser solving a JavaScript challenge, put
there by the STJ's own security coordination; the same endpoint answered on
2026-10-05. Harvesting access has to be asked for at `bdjur@stj.jus.br`, which
the protocol itself publishes. Until then `--de <pasta>` reads pages saved by
hand from a browser. Both paths parse the same `oai_dc` block with the same
code and produce the same rows; only the record header is read differently,
because the page the browser renders keeps it as text rather than as XML.
"""

import html
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import dlt
from dlt.sources.helpers import requests

OAI = "https://bdjur.stj.jus.br/server/oai/request"
REPOSITORIO = "bdjur"
CONJUNTOS = ("col_2011_8",)
PREFIXO = "oai_dc"
REQUEST_TIMEOUT = 300

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
XSI = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
HANDLE = "bdjur.stj.jus.br/handle/"

dlt.config["schema.naming"] = "direct"


def _campos(dc: ET.Element, nome: str) -> list[str]:
    valores = (
        re.sub(r"\s+", " ", e.text or "").strip() for e in dc.findall(f"dc:{nome}", NS)
    )
    return [v for v in valores if v]


# `dc:identifier` is never one value: the bibliographic reference and the
# permanent link share the tag, and a tenth of the records add an ISSN or a
# second link. Taking the first gives the reference where the link was wanted.
def _separa_identificadores(valores: list[str]) -> tuple[str | None, str | None]:
    link = next((v for v in valores if HANDLE in v), None) or next(
        (v for v in valores if v.startswith("http")), None
    )
    referencia = next(
        (
            v
            for v in valores
            if not v.startswith("http") and not v.replace("-", "").isdigit()
        ),
        None,
    )
    return referencia, link


# `dc:date` has the same problem, and worse consequences: the first value is
# always when the library filed the work, never when it was published. Every
# one of the 798 records in the sample opens with an accession timestamp, and
# 87% then give the year of publication — 1976 for a work filed in 2019. Taking
# the first would date every work by the digitisation and sort the list by it.
def _separa_datas(valores: list[str]) -> tuple[str | None, str | None]:
    publicacao = next(
        (v for v in valores if not re.match(r"\d{4}-\d{2}-\d{2}T", v)), None
    )
    return publicacao, next(iter(valores), None)


def _ano(data: str | None) -> int | None:
    achado = re.match(r"(1[5-9]\d{2}|20\d{2})", data or "")
    return int(achado.group(1)) if achado else None


# The protocol's own clock, and the cursor `from` compares against: when the
# record last changed, not when the work was published or filed. The two paths
# write it differently — the browser renders a space where the XML has a `T` —
# so it is normalised here, or the two forms would not sort against each other.
def _instante(bruto: str | None) -> str | None:
    limpo = (bruto or "").strip().replace(" ", "T").rstrip("Z")
    return (
        f"{limpo}Z"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", limpo)
        else None
    )


def _registro(
    identificador: str, alterada_em: str | None, conjuntos: list[str], dc: ET.Element
) -> dict[str, Any] | None:
    titulos = _campos(dc, "title")
    if not titulos:
        return None

    referencia, link = _separa_identificadores(_campos(dc, "identifier"))
    data, arquivada_em = _separa_datas(_campos(dc, "date"))
    return {
        "repositorio": REPOSITORIO,
        "identificador_oai": identificador,
        "alterada_em": alterada_em,
        "titulo": titulos[0],
        "titulos": titulos,
        "autores": _campos(dc, "creator"),
        "tipo": next(iter(_campos(dc, "type")), None),
        "data": data,
        "ano": _ano(data),
        "arquivada_em": arquivada_em,
        "idioma": next(iter(_campos(dc, "language")), None),
        "publicacao": next(iter(_campos(dc, "publisher")), None),
        "assuntos": _campos(dc, "subject"),
        "resumo": next(iter(_campos(dc, "description")), None),
        "referencia": referencia,
        "url_fonte": link,
        "direitos": next(iter(_campos(dc, "rights")), None),
        "conjuntos": conjuntos,
    }


def _do_xml(pagina: str) -> Iterator[dict[str, Any]]:
    raiz = ET.fromstring(pagina)
    for registro in raiz.iterfind(".//oai:record", NS):
        identificador = registro.findtext("oai:header/oai:identifier", namespaces=NS)
        dc = registro.find("oai:metadata/oai_dc:dc", NS)
        if not identificador or dc is None:
            continue

        conjuntos = [
            c.text.strip()
            for c in registro.iterfind("oai:header/oai:setSpec", NS)
            if c.text
        ]
        alterada_em = _instante(
            registro.findtext("oai:header/oai:datestamp", namespaces=NS)
        )
        linha = _registro(identificador.strip(), alterada_em, conjuntos, dc)
        if linha:
            yield linha


# The XSLT the repository ships for a reader escapes the XML as text and breaks
# every tag with a <span>. Undoing both gives the document back; the header
# does not survive as XML, so it is read from the text that replaced it.
_TAGS = re.compile(r"<[^>]+>")
_BLOCO = re.compile(r"<oai_dc:dc\b.*?</oai_dc:dc>", re.DOTALL)
_IDENTIFICADOR = re.compile(r"Identifier\s+(oai:\S+)")
_ALTERADA = re.compile(r"Last Modified\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")
_CONJUNTO = re.compile(r"\b(?:com|col)_\d+_\d+\b")


# Unescaped once, not twice: one pass gives back the XML the protocol sent,
# entities and all, which is what a parser wants. A second pass would turn an
# `&amp;` in a title into a bare `&` and stop the block from parsing at all.
def _desenfeita(bruto: str) -> str:
    return html.unescape(_TAGS.sub("", bruto))


def _da_pagina(bruto: str) -> Iterator[dict[str, Any]]:
    texto = _desenfeita(bruto)
    fim = 0
    for achado in _BLOCO.finditer(texto):
        cabecalho, fim = texto[fim : achado.start()], achado.end()

        # A deleted record is a header with no metadata of its own, so the text
        # before a block can hold more than one header: the last is this one's.
        marcas = list(_IDENTIFICADOR.finditer(cabecalho))
        if not marcas:
            continue
        cabecalho = cabecalho[marcas[-1].start() :]

        dc = ET.fromstring(f"<w {XSI}>{achado.group()}</w>").find("oai_dc:dc", NS)
        if dc is None:
            continue

        alterada = _ALTERADA.search(cabecalho)
        linha = _registro(
            marcas[-1].group(1),
            _instante(alterada.group(1)) if alterada else None,
            _CONJUNTO.findall(cabecalho),
            dc,
        )
        if linha:
            yield linha


def _paginas_do_endpoint(conjunto: str, desde: str | None) -> Iterator[str]:
    parametros = {"verb": "ListRecords", "metadataPrefix": PREFIXO, "set": conjunto}
    if desde:
        # Incremental collection is one argument: the repository sends back only
        # what changed since. 20.597 works is 206 pages, and a daily run that
        # asks for all of them to find the two that moved is rude to a host that
        # is lending us the data.
        parametros["from"] = desde
    while True:
        resposta = requests.get(OAI, params=parametros, timeout=REQUEST_TIMEOUT)
        resposta.raise_for_status()
        yield resposta.text

        token = ET.fromstring(resposta.text).findtext(
            ".//oai:resumptionToken", namespaces=NS
        )
        if not token or not token.strip():
            return
        # Once a token is in hand it is the only argument the protocol takes.
        parametros = {"verb": "ListRecords", "resumptionToken": token.strip()}


def _paginas_da_pasta(pasta: Path) -> Iterator[str]:
    paginas = sorted(p for p in pasta.iterdir() if p.is_file())
    if not paginas:
        raise RuntimeError(f"{pasta} has no saved pages to read")
    for pagina in paginas:
        yield pagina.read_text(encoding="utf-8", errors="replace")


# Merge, not replace: an incremental run brings back the handful of records
# that changed, and replacing the table with them would throw the other twenty
# thousand away. The key is the repository plus the OAI identifier.
#
# Nesting off keeps the four repeated fields as JSON on the row instead of
# four child tables. `data` is hinted text because a publication date is
# partial — `1976`, `2001-12`, `1997/1998` — and dlt would read some of those
# as timestamps and invent a day and a month for them.
@dlt.resource(
    name="doutrina_bdjur",
    write_disposition="merge",
    primary_key=("repositorio", "identificador_oai"),
    max_table_nesting=0,
    columns={"data": {"data_type": "text"}},
)
def doutrina(
    de: str | None = None,
    # O cursor no argumento é como o dlt lê e guarda o estado da coleta.
    alterada_em: dlt.sources.incremental[str] = dlt.sources.incremental(  # noqa: B008
        "alterada_em"
    ),
) -> Iterator[list[dict[str, Any]]]:
    total = 0
    for conjunto in CONJUNTOS:
        if de:
            paginas, lidas = _paginas_da_pasta(Path(de)), _da_pagina
        else:
            paginas, lidas = (
                _paginas_do_endpoint(conjunto, alterada_em.last_value),
                _do_xml,
            )

        for bruto in paginas:
            linhas = [linha for linha in lidas(bruto) if conjunto in linha["conjuntos"]]
            total += len(linhas)
            print(f"  {total} works so far", flush=True)
            if linhas:
                yield linhas


def main() -> None:
    de = sys.argv[sys.argv.index("--de") + 1] if "--de" in sys.argv else None
    de = de or os.getenv("BDJUR_PAGINAS") or None

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print(
        f"loading {REPOSITORIO} {CONJUNTOS[0]}{f' from {de}' if de else ''}", flush=True
    )
    print(pipeline.run(doutrina(de)))


if __name__ == "__main__":
    main()
