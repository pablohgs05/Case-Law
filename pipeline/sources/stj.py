"""
Espelhos de acórdãos from the STJ's open data portal.

Not an API that pages: a CKAN catalogue of files. Each of the eleven datasets —
one per turma and seção — carries a ZIP with the whole history and monthly JSON
files with what came after. The same acórdão can appear in two files, and `id`
is what tells them apart.

Published under Creative Commons Attribution.
"""

import io
import json
import os
import zipfile
from collections.abc import Iterator
from typing import Any

import dlt
from dlt.sources.helpers import requests

CKAN = "https://dadosabertos.web.stj.jus.br/api/3/action"
REQUEST_TIMEOUT = 300

DATASETS = (
    "espelhos-de-acordaos-corte-especial",
    "espelhos-de-acordaos-primeira-secao",
    "espelhos-de-acordaos-primeira-turma",
    "espelhos-de-acordaos-quarta-turma",
    "espelhos-de-acordaos-quinta-turma",
    "espelhos-de-acordaos-segunda-secao",
    "espelhos-de-acordaos-segunda-turma",
    "espelhos-de-acordaos-sexta-turma",
    "espelhos-de-acordaos-terceira-secao",
    "espelhos-de-acordaos-terceira-turma",
)

BATCH = 2000

dlt.config["schema.naming"] = "direct"


def _resources(dataset: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{CKAN}/package_show", params={"id": dataset}, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return list(response.json()["result"]["resources"])


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def _from_json(url: str) -> list[dict[str, Any]]:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return _records(json.loads(response.content))


def _from_zip(url: str) -> Iterator[list[dict[str, Any]]]:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".json"):
                continue
            with archive.open(name) as handle:
                yield _records(json.loads(handle.read()))


def _files(dataset: str) -> Iterator[tuple[str, str, str]]:
    """Every file worth reading, as (kind, name, url)."""
    for resource in _resources(dataset):
        formato = (resource.get("format") or "").upper()
        nome = resource.get("name") or ""
        if formato == "ZIP":
            yield "zip", nome, resource["url"]
        elif formato == "JSON":
            yield "json", nome, resource["url"]


@dlt.resource(
    name="espelho_stj",
    write_disposition="merge",
    primary_key="id",
)
def espelhos(datasets: tuple[str, ...] = DATASETS) -> Iterator[list[dict[str, Any]]]:
    ilegiveis: list[tuple[str, str, int]] = []
    vazios = 0

    for dataset in datasets:
        orgao = dataset.removeprefix("espelhos-de-acordaos-")
        arquivos = list(_files(dataset))
        print(f"{orgao}: {len(arquivos)} files", flush=True)
        lidos = 0

        for kind, nome, url in arquivos:
            lidos += 1
            if lidos % 10 == 0:
                print(f"  {orgao}: {lidos}/{len(arquivos)}", flush=True)
            try:
                lotes = list(_from_zip(url)) if kind == "zip" else [_from_json(url)]
            except json.JSONDecodeError as erro:
                tamanho = int(requests.head(url, timeout=60).headers.get("content-length", 0))
                ilegiveis.append((orgao, nome, tamanho))
                print(f"  unreadable: {orgao}/{nome} ({tamanho} bytes) — {erro}", flush=True)
                continue

            for registros in lotes:
                # The source publishes a placeholder for a month with nothing
                # new. It has no id, and an id is what tells two copies apart.
                uteis = [r for r in registros if str(r.get("id") or "").strip()]
                vazios += len(registros) - len(uteis)
                if not uteis:
                    continue
                for r in uteis:
                    r["_orgao_conjunto"] = orgao
                    r["_arquivo"] = nome
                for i in range(0, len(uteis), BATCH):
                    yield uteis[i : i + BATCH]

    if vazios:
        print(f"  {vazios} placeholder records without an id, skipped", flush=True)
    if ilegiveis:
        print(f"  {len(ilegiveis)} files could not be read:", flush=True)
        for orgao, nome, tamanho in ilegiveis:
            print(f"    {orgao}/{nome}  {tamanho} bytes", flush=True)


def main() -> None:
    somente = os.getenv("STJ_DATASETS", "").strip()
    escolhidos = tuple(somente.split(",")) if somente else DATASETS

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print(f"loading {len(escolhidos)} datasets", flush=True)
    print(pipeline.run(espelhos(escolhidos)))


if __name__ == "__main__":
    main()
