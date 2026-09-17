# Processo de testes unitários

## Objetivo

Aplicar testes automatizados nas partes do código que possuem lógica, para
encontrar regressões e registrar um resultado repetível antes da entrega.

## Unidade escolhida

O alvo atual é `backend/app/config.py`, especialmente a classe `Settings`.
Ela transforma `CORS_ORIGINS` em uma lista e lê `ENVIRONMENT`. Infraestrutura
como banco, servidor e navegador não faz parte deste escopo.

## Casos testados

Os quatro cenários ficam em `backend/tests/test_config.py`:

- valor padrão de `CORS_ORIGINS`;
- uma origem configurada;
- várias origens separadas por vírgula;
- leitura de `ENVIRONMENT`.

Os cenários seguem **Given / When / Then**. O `monkeypatch` simula variáveis de
ambiente durante o teste e restaura o estado depois. Não há dependência externa
que exija mock.

## Execução

```bash
cd backend
uv sync --locked
uv run pytest -m unit -v
```

Resultado validado: `4 passed`.

## Relação com DevOps

```text
Código alterado
    ↓
Teste unitário
    ↓
Resultado aprovado ou falho
    ↓
Correção, se necessário
    ↓
Código pronto para a próxima etapa
```

Esta entrega fornece os testes e o comando reproduzível. CI, integração e
cobertura por ferramenta externa não fazem parte desta etapa.

Cobertura ajuda a encontrar código sem teste, mas não garante qualidade
perfeita; os cenários também precisam verificar comportamentos importantes.
