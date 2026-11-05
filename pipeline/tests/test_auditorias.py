"""
Que toda auditoria citada por um modelo exista de verdade.

O SQLMesh não reclama de um nome que não resolve: a auditoria simplesmente não
roda. Um erro de digitação na lista do bloco MODEL desliga a regra em silêncio,
e a carga continua passando — que é o pior jeito de perder uma garantia.
"""

import re
from pathlib import Path

TRANSFORMACOES = Path(__file__).resolve().parents[1] / "transformations"
MODELOS = sorted((TRANSFORMACOES / "models").glob("*.sql"))
REGRAS = TRANSFORMACOES / "audits" / "regras.sql"

# As que o SQLMesh traz prontas; não estão em regras.sql e não precisam estar.
EMBUTIDAS = {
    "not_null",
    "unique_values",
    "unique_combination_of_columns",
    "accepted_values",
}


def declaradas() -> set[str]:
    return set(
        re.findall(
            r"AUDIT \(\s*name\s+([a-z_]+)\s*,", REGRAS.read_text(encoding="utf-8")
        )
    )


def citadas(modelo: Path) -> set[str]:
    texto = modelo.read_text(encoding="utf-8")
    bloco = re.search(r"audits\s*\((.*?)\n\s*\)\s*\n\);", texto, re.DOTALL)

    if not bloco:
        return set()

    # Os argumentos saem antes: `not_null(columns := (a, b))` traz nomes de
    # coluna que não são auditoria nenhuma.
    lista = re.sub(r"\([^()]*(?:\([^()]*\)[^()]*)*\)", "", bloco.group(1))
    nomes = re.findall(r"[a-z_]+", lista)
    return {nome for nome in nomes if nome not in EMBUTIDAS}


def test_toda_auditoria_citada_existe() -> None:
    existentes = declaradas()
    faltando = {
        modelo.name: sorted(citadas(modelo) - existentes)
        for modelo in MODELOS
        if citadas(modelo) - existentes
    }

    assert not faltando, f"auditorias citadas e inexistentes: {faltando}"


def test_nenhuma_auditoria_fica_sem_uso() -> None:
    """
    O contrário também engana: uma regra escrita e nunca citada parece proteger
    e não protege nada.
    """
    usadas = set().union(*(citadas(modelo) for modelo in MODELOS))

    assert not declaradas() - usadas


def test_o_link_oficial_tem_auditoria() -> None:
    """A regra da SCRUM-180, presa ao modelo que ela guarda."""
    decisao = TRANSFORMACOES / "models" / "core_decisao.sql"

    assert "url_aponta_para_um_acordao" in citadas(decisao)
