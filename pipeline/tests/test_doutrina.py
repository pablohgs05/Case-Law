"""
What the BDJur collector reads out of a record.

Two readers, one shape. The protocol's XML is what will be read the day
harvesting access is granted; the page saved from a browser is what can be read
today. The test that matters most is that they agree field by field — without
it the stopgap and the real path would be two different collectors, and only
one of them would ever be exercised.

Six real records, each in the fixture for a trap it carries: a `dc:identifier`
that appears three times, a `dc:date` that opens with the filing timestamp, a
deleted record sitting between two live ones, a restricted work filed in the
open-access collection, a link through the canonical Handle resolver, and an
`&` escaped twice over by the time it reaches the page.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from sources import doutrina

FIXTURES = Path(__file__).parent / "fixtures"
PAGINA = (FIXTURES / "bdjur_pagina.html").read_text(encoding="utf-8")
RESPOSTA = (FIXTURES / "bdjur_resposta.xml").read_text(encoding="utf-8")

APAGADO = "oai:bdjur.stj.jus.br:2011/114535"
SEGUINTE = "oai:bdjur.stj.jus.br:2011/127476"
COM_ISSN = "oai:bdjur.stj.jus.br:2011/217041"
COM_E_COMERCIAL = "oai:bdjur.stj.jus.br:2011/156039"
RESTRITA = "oai:bdjur.stj.jus.br:2011/38622"
PELO_RESOLVEDOR = "oai:bdjur.stj.jus.br:2011/18979"


def _por_id(linhas: Iterator[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {linha["identificador_oai"]: linha for linha in linhas}


@pytest.fixture(params=["protocolo", "pagina salva"])
def obras(request: pytest.FixtureRequest) -> dict[str, dict[str, Any]]:
    """Every assertion below runs twice, once against each reader."""
    if request.param == "protocolo":
        return _por_id(doutrina._do_xml(RESPOSTA))
    return _por_id(doutrina._da_pagina(PAGINA))


def test_as_duas_leituras_entregam_a_mesma_linha() -> None:
    """
    O teste que sustenta o resto. Enquanto o endpoint recusa acesso
    automatizado, a coleta sai de páginas salvas do navegador; no dia em que o
    acesso voltar, sai do XML do protocolo. Se as duas leituras divergirem em
    um campo, metade do acervo entra num formato e metade no outro, e nada
    falha.
    """
    assert list(doutrina._do_xml(RESPOSTA)) == list(doutrina._da_pagina(PAGINA))


def test_o_link_sai_do_identificador_certo(obras: dict[str, dict[str, Any]]) -> None:
    """
    `dc:identifier` aparece três vezes neste registro: a referência
    bibliográfica, o ISSN e o link permanente. Pegar o primeiro valor põe a
    referência onde devia estar o link, e ninguém descobre até clicar.
    """
    obra = obras[COM_ISSN]

    assert obra["url_fonte"] == "https://bdjur.stj.jus.br/handle/2011/217041"
    assert obra["referencia"] == (
        "Revista Direito e Liberdade: RDL, Natal, v. 28, n. 1, jan./abr. 2026."
    )
    assert "21771758" not in (obra["referencia"], obra["url_fonte"])


def test_o_link_de_cada_obra_aponta_para_o_proprio_registro(
    obras: dict[str, dict[str, Any]],
) -> None:
    for identificador, obra in obras.items():
        assert identificador.split(":")[-1] in obra["url_fonte"], identificador


def test_a_data_e_a_da_publicacao_nao_a_do_arquivamento(
    obras: dict[str, dict[str, Any]],
) -> None:
    """
    Treze anos de diferença num registro só. O primeiro `dc:date` é quando a
    biblioteca arquivou a obra, e trocar um pelo outro não dá erro: enche a
    coluna de datas recentes e ordena a lista pela digitalização.
    """
    obra = obras[PELO_RESOLVEDOR]

    assert obra["data"] == "1995"
    assert obra["ano"] == 1995
    assert obra["arquivada_em"].startswith("2008-")


def test_nenhuma_data_de_publicacao_e_um_instante(
    obras: dict[str, dict[str, Any]],
) -> None:
    """A regra por trás do caso acima, sobre todos os registros."""
    for identificador, obra in obras.items():
        assert not re.match(r"\d{4}-\d{2}-\d{2}T", obra["data"] or ""), identificador


def test_o_registro_apagado_nao_entra(obras: dict[str, dict[str, Any]]) -> None:
    """Cabeçalho com `status="deleted"` e nenhum metadado: não há obra a mostrar."""
    assert APAGADO not in obras


def test_o_registro_apagado_nao_desloca_o_seguinte(
    obras: dict[str, dict[str, Any]],
) -> None:
    """
    O defeito que este caso pegou. O apagado não traz bloco de metadado, então
    o cabeçalho dele sobra junto do cabeçalho do registro seguinte — e o
    seguinte passa a responder pelo identificador e pelas coleções do apagado.
    Dois dos 800 registros da amostra são apagados, e os dois ficam no meio da
    lista.
    """
    obra = obras[SEGUINTE]

    assert obra["conjuntos"] == ["com_2011_2", "col_2011_8"]
    assert obra["titulo"].startswith("La necesidad de cambios")
    assert obra["alterada_em"] == "2026-05-18T12:52:07Z"


def test_os_direitos_chegam_como_a_biblioteca_escreveu(
    obras: dict[str, dict[str, Any]],
) -> None:
    """
    Uma obra arquivada em Acesso Aberto declara "Restricted access" no próprio
    `dc:rights`. Quem decide é o modelo, não o extrator: a camada bruta grava o
    que a fonte disse, sem interpretar, senão recarregar deixa de ser suficiente
    para voltar atrás.
    """
    assert obras[RESTRITA]["direitos"] == "Restricted access"


def test_o_e_comercial_sobrevive(obras: dict[str, dict[str, Any]]) -> None:
    """
    `&` chega à página escapado duas vezes: uma pelo XML, outra pelo HTML que o
    renderiza. Desescapar as duas de uma vez devolve um `&` solto e o bloco
    para de ser XML válido — o registro inteiro desaparece sem erro.
    """
    referencia = obras[COM_E_COMERCIAL]["referencia"]

    assert referencia.startswith("Justiça & Cidadania")
    assert "&amp;" not in referencia


def test_toda_obra_traz_o_cursor_do_protocolo(
    obras: dict[str, dict[str, Any]],
) -> None:
    """Sem `alterada_em` não há coleta incremental: o `from` não tem o que comparar."""
    for identificador, obra in obras.items():
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", obra["alterada_em"]
        ), identificador


def test_so_a_colecao_de_acesso_aberto_e_pedida() -> None:
    """
    O escopo da história, no código. col_2011_9 é Acesso Restrito, e a
    separação é da própria biblioteca.
    """
    assert doutrina.CONJUNTOS == ("col_2011_8",)


def test_a_pagina_seguinte_vem_pelo_resumption_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pedidos: list[dict[str, str]] = []
    paginas = [
        RESPOSTA,
        RESPOSTA.replace(
            '<resumptionToken completeListSize="20597" cursor="0">'
            "oai_dc///col_2011_8/100</resumptionToken>",
            "<resumptionToken />",
        ),
    ]

    def falso_get(url: str, params: dict[str, str], timeout: int) -> Any:
        pedidos.append(dict(params))
        return type(
            "Resposta",
            (),
            {"text": paginas[len(pedidos) - 1], "raise_for_status": lambda self: None},
        )()

    monkeypatch.setattr(doutrina.requests, "get", falso_get)
    lidas = list(doutrina._paginas_do_endpoint("col_2011_8", None))

    assert len(lidas) == 2
    assert pedidos[0]["set"] == "col_2011_8"
    # Com token na mão, o protocolo não aceita mais nenhum outro argumento.
    assert pedidos[1] == {
        "verb": "ListRecords",
        "resumptionToken": "oai_dc///col_2011_8/100",
    }


def test_a_coleta_incremental_pede_so_o_que_mudou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    206 páginas para achar as duas que mudaram é falta de educação com um
    servidor que está emprestando os dados.
    """
    pedidos: list[dict[str, str]] = []

    def falso_get(url: str, params: dict[str, str], timeout: int) -> Any:
        pedidos.append(dict(params))
        return type(
            "Resposta",
            (),
            {"text": "<OAI-PMH />", "raise_for_status": lambda self: None},
        )()

    monkeypatch.setattr(doutrina.requests, "get", falso_get)

    list(doutrina._paginas_do_endpoint("col_2011_8", "2026-05-18T12:52:07Z"))
    assert pedidos[0]["from"] == "2026-05-18T12:52:07Z"

    pedidos.clear()
    list(doutrina._paginas_do_endpoint("col_2011_8", None))
    assert "from" not in pedidos[0]


def test_o_instante_do_protocolo_fica_num_formato_so() -> None:
    """
    O navegador escreve um espaço onde o XML escreve `T`. Duas formas na mesma
    coluna param de ordenar entre si, e o cursor da coleta incremental é
    exatamente uma comparação de ordem.
    """
    assert doutrina._instante("2026-05-18 12:52:07") == "2026-05-18T12:52:07Z"
    assert doutrina._instante("2026-05-18T12:52:07Z") == "2026-05-18T12:52:07Z"
    assert doutrina._instante("") is None
    assert doutrina._instante(None) is None


def test_a_colecao_restrita_nunca_e_colhida(tmp_path: Path) -> None:
    """
    O compromisso com o cliente, no extrator. Uma resposta contendo registros
    de col_2011_9 — Acesso Restrito — não deixa nenhum deles entrar, por mais
    que o conjunto aberto também esteja no mesmo cabeçalho.

    O recurso filtra pelo conjunto pedido, e `CONJUNTOS` é a lista inteira do
    que pode ser pedido. As duas afirmações juntas são a regra; o modelo
    `core.doutrina` a repete na camada seguinte, de propósito.
    """
    restrita = RESPOSTA.replace(
        "<setSpec>col_2011_8</setSpec>", "<setSpec>col_2011_9</setSpec>"
    )
    lidas = list(doutrina._do_xml(restrita))

    assert lidas, "a leitura em si não filtra: quem filtra é a coleta"
    for obra in lidas:
        assert "col_2011_8" not in obra["conjuntos"]
        assert obra["conjuntos"].count("col_2011_9") >= 1

    # E col_2011_9 não está entre os conjuntos que a coleta pede.
    assert "col_2011_9" not in doutrina.CONJUNTOS


def test_a_obra_sem_resumo_entra_com_resumo_nulo() -> None:
    """
    68% dos registros não trazem `dc:description`. Descartá-los por isso
    jogaria fora dois terços do acervo.
    """
    obras = _por_id(doutrina._do_xml(RESPOSTA))
    sem_resumo = [o for o in obras.values() if o["resumo"] is None]

    assert sem_resumo, "a amostra precisa de um registro sem resumo"
    for obra in sem_resumo:
        assert obra["titulo"]
        assert obra["url_fonte"]


def test_recolher_de_novo_nao_duplica() -> None:
    """
    A carga é `merge` sobre repositório mais identificador OAI, não `replace`
    nem `append`. Com `append`, rodar a coleta duas vezes dobraria o acervo; com
    `replace`, uma coleta incremental — que traz só o que mudou — apagaria o
    resto.
    """
    hints = doutrina.doutrina._hints

    assert hints["write_disposition"] == "merge"
    assert tuple(hints["primary_key"]) == ("repositorio", "identificador_oai")

    # E a chave é de fato única no que a leitura entrega.
    lidas = list(doutrina._do_xml(RESPOSTA)) * 2
    chaves = {(o["repositorio"], o["identificador_oai"]) for o in lidas}

    assert len(chaves) == len(lidas) // 2
