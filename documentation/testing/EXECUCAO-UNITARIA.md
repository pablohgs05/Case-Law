# Execução verificada — 22/10/2026

Código da contribuição testado: d67dee134efdef4acf57727730ce7eaa03f9e4b8, criado sobre dev 5eb90ab070d6d27c230d96913643fd4e1c82bbee. Commits posteriores nesta contribuição acrescentam somente documentos/logs; comparar diff para confirmar. Windows; Python 3.12.14; Pytest 9.1.1; Vitest 2.1.9. Dependências frontend reinstaladas do lock atual com npm ci --ignore-scripts, sem alteração do manifesto/lock. A ausência inicial de recharts no ambiente antigo foi resolvida com essa reinstalação; types passou depois.

| Verificação | Comando (na pasta indicada) | Resultado |
|---|---|---|
| Backend focal | backend: .venv/Scripts/python.exe -m pytest tests/test_scrum_ementa_bdd.py -m unit -q | 4 aprovados, 0 falhos, 0 ignorados |
| Regressão backend selecionada | backend: .venv/Scripts/python.exe -m pytest tests/test_ementa.py tests/test_config.py tests/test_scrum_ementa_bdd.py -q | 105 aprovados, 0 falhos, 0 ignorados |
| Frontend focal | frontend: node node_modules/vitest/vitest.mjs run src/tests/scrumCardBdd.test.tsx | 3 aprovados |
| Frontend completo | frontend: node node_modules/vitest/vitest.mjs run | 221 aprovados em 19 arquivos |
| Python | backend: ruff check app tests scripts; ruff format --check dos 2 arquivos novos; mypy app tests, via .venv/Scripts/python.exe -m | aprovados; mypy 38 arquivos |
| Frontend qualidade | frontend: node node_modules/typescript/bin/tsc -b --pretty false; eslint . --max-warnings 0; prettier --check src/tests/scrumCardBdd.test.tsx | aprovados |
| Ensaio repetível | backend: .venv/Scripts/python.exe scripts/demo_test_cycle.py | 4 falhas esperadas → restauração → 4 aprovados; saída final 0 |

[Logs desta execução](evidence/fluxo). Contagens antigas 166/184 se referem à branch anterior e não são reutilizadas para esta branch. O marcador unit foi declarado apenas para os novos testes focais; não se afirma que -m unit seleciona toda a suíte histórica de dev.

## Prova no histórico do sandbox

[PR #3](https://github.com/pablohgs05/Case-Law/pull/3): sandbox/unitarios-ciclo → sandbox/unitarios-base. Nunca integrar. Base d67dee1.

- [Defeito deliberado ed77944](https://github.com/pablohgs05/Case-Law/commit/ed77944db874a9f4b6e0c91baea0e9343ea0bbe9): ordem caso/questão invertida na classe, testes intactos. Execução local com pytest -c backend/pyproject.toml backend/tests/test_scrum_ementa_bdd.py -q -o pythonpath=backend: 4 falhos, saída 1. Log vermelho.txt. O run automático 39824705498 foi cancelado por concorrência após o push da correção; não é apresentado como CI vermelho concluído.
- [Correção a65f469](https://github.com/pablohgs05/Case-Law/commit/a65f4691b302944e110eb6ab5c0e75f02c0bab49): implementação restaurada em novo commit, sem alterar os testes. Mesmo comando: 4 aprovados, saída 0. Log verde.txt. [CI da correção](https://github.com/pablohgs05/Case-Law/actions/runs/39824742488): success.
- Entre base e correção, app/ementa.py termina idêntico. O histórico preserva os dois commits; não houve reset/rebase/force-push. Não representa falha descoberta no produto ou devolução humana.

## CI da contribuição

[CI do código d67dee1](https://github.com/pablohgs05/Case-Law/actions/runs/39824620373): success. O guard de main/producao não se aplica à base dev. Conferir também Checks do head documental atual na PR #2; sucesso antigo não é aprovação automática de commits novos.

O CI preexistente executa a suíte histórica com banco de serviço. Isso não encerra a entrega de integração separada nem converte os 195 ignorados históricos em aprovados. Não rodamos a entrega própria de integração nesta fase.

## Pendências humanas

Ratificação dos critérios/vínculos da planning e review por colega na própria conta: pendentes. Sem review, sem decisão de merge e sem DoD completo. main/dev, workflows, proteção, ReqTrack e código dos colegas preservados.

## Wiki publicada e verificação posterior

Wiki sincronizada no fork em d9501e647310294668ebb6abd2da80ae51d6ff47, com push confirmado e ls-remote conferido. A anotação Fluxo-de-teste-unitario.md não sofreu alteração. Cópias publicadas em wiki-preparada/. Nenhuma ação manual de Wiki é necessária nesta execução.

CI documental c825b97: [success](https://github.com/pablohgs05/Case-Law/actions/runs/39825276481). Sandbox final 045783a: [success](https://github.com/pablohgs05/Case-Law/actions/runs/39825386342). Nova publicação documental exige conferir o head mais recente na aba Checks.
