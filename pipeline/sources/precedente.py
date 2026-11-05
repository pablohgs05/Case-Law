"""
Qualified precedents from the STJ's open data portal.

The same CKAN catalogue the espelhos come from, under another dataset. Two
thousand rows against a million decisions, so it loads whole on every run
instead of paging.

Published under Creative Commons Attribution.
"""

import csv
import io
import os
from collections.abc import Iterator
from typing import Any

import dlt
from dlt.sources.helpers import requests

CKAN = "https://dadosabertos.web.stj.jus.br/api/3/action"
DATASET = "precedentes-qualificados"
REQUEST_TIMEOUT = 300

TEMAS = "temas.csv"
PROCESSOS = "processos.csv"

dlt.config["schema.naming"] = "direct"


def _resource_url(nome: str) -> str:
    response = requests.get(
        f"{CKAN}/package_show", params={"id": DATASET}, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    for recurso in response.json()["result"]["resources"]:
        # A barra importa: `dicionario-temas.csv` também termina em `temas.csv`.
        if str(recurso.get("url", "")).lower().endswith(f"/{nome}"):
            return str(recurso["url"])

    raise RuntimeError(f"{DATASET} no longer carries {nome}")


def _rows(nome: str) -> list[dict[str, Any]]:
    response = requests.get(_resource_url(nome), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    response.encoding = "utf-8-sig"

    lido = csv.DictReader(io.StringIO(response.text))
    return [{k: v for k, v in linha.items() if k} for linha in lido]


@dlt.resource(name="precedente_stj", write_disposition="replace")
def temas() -> Iterator[list[dict[str, Any]]]:
    linhas = _rows(TEMAS)
    print(f"  {len(linhas)} qualified precedents", flush=True)
    yield linhas


@dlt.resource(name="precedente_processo_stj", write_disposition="replace")
def processos() -> Iterator[list[dict[str, Any]]]:
    linhas = _rows(PROCESSOS)
    print(f"  {len(linhas)} processes bound to a precedent", flush=True)
    yield linhas


def main() -> None:
    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print(f"loading {DATASET}", flush=True)
    recursos = [temas()]
    if os.getenv("PRECEDENTE_PROCESSOS", "").strip().lower() not in ("", "0", "false"):
        recursos.append(processos())
    print(pipeline.run(recursos))


if __name__ == "__main__":
    main()
