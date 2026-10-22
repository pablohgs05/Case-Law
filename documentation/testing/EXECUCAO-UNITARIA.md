# Execução unitária — 22/10/2026

Código publicado: `c4fe50c079aa3a2550c6e8092c8191ecf109a2af`; árvore `8a345066fce5ee309ad9b64abb437b947e67759a`, idêntica ao commit local anterior cb46e0b (backup/unitarios-local-20261022). Publicado pelo conector porque Git/HTTPS encerra conexão. Commit remoto incorporado localmente por SHA verificado, sem alterar arquivos. Evidências adicionadas depois não alteram código/testes executados.

## Resultado real

| Verificação | Resultado | Log |
|---|---|---|
| Classe focal StructuredEmenta.rebuild | 4 aprovados | [roteiro](evidence/apresentacao-atual.txt) |
| Componente focal DecisionResultCard | 3 aprovados | mesmo roteiro |
| Defeito na classe temporária, com teste intacto | 4 falhas deliberadas; restaurada a classe, 4 aprovados; script retorna 0 | mesmo roteiro |
| Backend unitário completo | 166 aprovados, 195 não selecionados, zero falhas | [backend](evidence/backend-unit-atual.txt) |
| Frontend completo | 184 aprovados / 16 arquivos, zero falhas | [frontend](evidence/frontend-atual.txt) |
| Tipos frontend | tsc -b, saída 0 | checagem local |
| Ruff dos três arquivos Python alterados | aprovado após ajuste de imports | checagem local |
| Script de apresentação inteiro | saída 0; repetido no SHA publicado | [logs e contexto](evidence/unitarios/) |

Comandos na raiz para a demonstração: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1`. Backend completo a partir de backend: `.venv/Scripts/python.exe -m pytest -m unit -q`. Frontend a partir de frontend: `node node_modules/vitest/vitest.mjs run` e `node node_modules/typescript/bin/tsc -b`. Ruff em backend: `.venv/Scripts/python.exe -m ruff check scripts/demo_test_cycle.py tests/test_scrum_ementa_bdd.py tests/test_scrum_ementa_integration.py`.

Windows, Python 3.12.14, pytest 9.1.1, Vitest 2.1.9. Dependências existentes, sem atualizações. Avisos de depreciação backend/React Router/act existentes não são falhas. Frontend completo inclui páginas/utilitários históricos; sua contagem não equivale a testes de componentes isolados. Frontend completo rodou na mesma árvore antes de publicar. A última pasta de logs tem o contexto do commit remoto; anteriores são ensaios intermediários. O primeiro ensaio precedeu ajuste da mensagem de contagem/encoding.

## Pendências reais

- Devs ratificarem critérios, classes, vínculos SCRUM-18/20 e SCRUM-50/55, sprint, estimativas e responsáveis na planning. Usar [ficha](PLANNING-E-REVISAO.md).
- Outro integrante repetir/conferir e registrar decisão na PR. Não houve review humano, devolução ou aprovação; ensaio não substitui essas etapas.
- DoD exige também CI verde antes de merge; esta execução local não certifica CI e não o altera.
- [Integração posterior](INTEGRACAO-POSTERIOR.md): compose isolado preparado, não executado por ausência de Docker/PostgreSQL/TEST_DATABASE_URL. Os 195 ignorados históricos não são aprovação; integração não integra a aula unitária.
- Wiki: duas páginas atualizadas e commitadas no clone local (e297fca); anotação original do professor intacta. Publicação bloqueada por conexão encerrada também no navegador; conector não edita Wiki. [Cópias prontas](wiki-preparada/) entregues nesta PR para uso imediato. Quando a conexão voltar, em Case-Law.wiki executar `git fetch origin`, conferir divergência e então `git push origin HEAD`, somente no fork; sem force push.

PR #1 preservada em draft. main/dev, commits e backups anteriores preservados; nenhum push/PR no original. CI/ReqTrack intactos. Nenhuma sincronização agendada criada. Integração anterior preservada em arquivo próprio; evidências anteriores preservadas como históricas.
