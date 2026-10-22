# Evidências — 22/10/2026

## Sincronização

- Fork: https://github.com/pablohgs05/Case-Law
- Original consultado: https://github.com/Praxis-Fatec/Case-Law
- Fork anterior: `166cd47f15ef022c03714c53613f18ebf2c6c59a` (backup remoto `backup/fork-before-sync-20261022`).
- Upstream incorporado: `9587dc77fa47254c517277e4ae5dc11b93f337ba`.
- Merge publicado no main do fork: `d6cfb771a31fd4585163f31fe19689243797b87b`, sem conflitos. Oito commits próprios preservados e oito commits do original incorporados.
- Upstream configurado localmente com URL de push `DISABLED`. Nenhum push ou PR direcionado ao original.
- Wiki lida integralmente: `Home.md` e `Fluxo-de-teste-unitario.md`; SHA inicial `e9262917359ce6e3ce53fe8bc34d1b3978c129db`. A anotação original do professor permanece intacta; a aplicação é acrescentada em página separada e vinculada na Home.

## Ambiente e comandos

Windows, Python 3.12.14, pytest 9.1.1, Vitest 2.1.9. Backend instalado com `uv sync --locked` no ambiente virtual do projeto. Frontend instalado do `package-lock.json` com `npm ci --ignore-scripts`, via npm disponibilizado pelo gerenciador local. Não houve alteração dos arquivos de dependências.

Os comandos equivalentes usados localmente foram `.venv/Scripts/python.exe -m pytest ...` no backend e `node node_modules/vitest/vitest.mjs run` no frontend, pois uv/npm não estavam no PATH inicial. Para os colegas, os comandos usuais estão em TESTING.md.

| Verificação | Resultado | Evidência |
|---|---|---|
| Backend `pytest -m unit -q` | 165 aprovados, 195 não selecionados | [backend-unit.txt](evidence/backend-unit.txt) |
| Backend `pytest -m integration -q -rs` | 195 ignorados, 165 não selecionados; **não aprovado** | [backend-integration.txt](evidence/backend-integration.txt) |
| Frontend `vitest run` | 184 testes / 16 arquivos aprovados na execução final | [frontend.txt](evidence/frontend.txt) |
| Ensaio `python scripts/demo_test_cycle.py` | 3 falhas deliberadas, correção na cópia e 3 aprovados; script retorna 0 | [ciclo.txt](evidence/ciclo.txt) |
| TypeScript `tsc -b` | aprovado após corrigir entrada do teste novo | checagem local |
| Ruff nos dois novos arquivos Python | aprovado | checagem local |
| Prettier nos testes frontend alterados | aprovado | checagem local |

Os logs correspondem ao código dos testes entregue nesta PR. O commit que os contém é o commit testado (os logs e este texto são evidência documental). As três falhas do ensaio são intencionais, não defeitos do sistema.

## Falha real observada e correção

A primeira execução completa do frontend aprovou 184 testes. Uma repetição com relatório JSON teve 183 aprovados e uma falha em `decisionDetail.test.tsx`, cenário `falls back to the whole text when a section comes back empty`. O DOM ainda mostrava `Carregando decisão...`; a espera por um heading nível 2 retornava antes da resposta porque esse heading também existe no carregamento. O relatório original está em [frontend-antes-correcao.json](evidence/frontend-antes-correcao.json).

Correção restrita ao teste: `renderDetail` passa a aguardar `aria-busy=false` com `waitFor`, sem atraso fixo e sem alterar a aplicação. A nova suíte completa deve ser conferida em `frontend.txt`. Isso documenta falha → correção pelo autor → nova execução, mas não representa solicitação de alterações nem aprovação de outro revisor.

A checagem de tipos também identificou inicialmente props inválidas no teste novo (`decided_on` e snippet nulos); as entradas foram ajustadas ao contrato real da API, mantendo três casos válidos: vazio, espaços e quebra de linha.

## Bloqueios e próximos responsáveis

1. Integração: `TEST_DATABASE_URL` ausente; Docker/psql não encontrados no PATH e nenhuma instalação padrão de PostgreSQL encontrada. Não foi usado banco remoto nem dados de produção. Preparar PostgreSQL de teste com pgvector, pg_trgm e unaccent e repetir os 195 testes; instruções em TESTING.md. Não alegar aprovação pela saída 0 de pytest quando tudo foi ignorado.
2. Planning: a tabela é proposta ligada às histórias existentes, ainda depende de ratificação pelos devs, sprint e responsáveis. Nenhum registro Scrum/ReqTrack foi alterado.
3. Revisão: outro integrante deve revisar e decidir. Não houve autoaprovação nem fabricação de review. A PR fica em rascunho enquanto integração e revisão estiverem pendentes.

Avisos observados: depreciação do BlockingPortal no backend e avisos de React Router/act em testes existentes. A instalação npm reportou 10 vulnerabilidades (5 moderadas, 2 altas, 3 críticas); nenhuma atualização de dependência ou configuração de CI foi incluída neste recorte.
