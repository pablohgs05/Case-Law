# Roteiro — 6 a 8 minutos

## 1. Contexto (1 min)

Abrir o fork e a Wiki. Explicar: “Minha responsabilidade são os testes e o fluxo de evidência/revisão. A equipe define critérios na planning. CI e ReqTrack são de outros responsáveis.” Mostrar a anotação original do professor, que foi preservada.

## 2. Planning (1 min)

Abrir a tabela de TESTING.md. Explicar que é uma proposta demonstrativa a ratificar com os devs, sem alegar reunião que não aconteceu. Mostrar C1/StructuredEmenta.rebuild (classe utilitária), C2/API + banco real e C3/DecisionResultCard (componente). Dar exemplo Dado/Quando/Então de cada um.

## 3. Testes (2 min)

Em backend, executar `uv run pytest tests/test_scrum_ementa_bdd.py -m unit -v` e abrir o teste: contexto, ação e expectativa. Mostrar que acentos/espaços e ordem são preservados. Em frontend, executar `npm test -- src/tests/scrumCardBdd.test.tsx` e mostrar a orientação para trecho ausente.

Explicar que BDD é descrever comportamento verificável; estes testes usam Dado/Quando/Então em Pytest/Vitest, sem exigir Cucumber.

## 4. Falha, correção, nova execução (1 min)

Em backend, executar `uv run python scripts/demo_test_cycle.py`. Mostrar expectativa deliberadamente errada falhando numa cópia temporária e a expectativa correta passando. Dizer explicitamente: “Este é um ensaio técnico. A devolução e aprovação da PR precisam de outro integrante de verdade.”

## 5. Integração e limite da evidência (1 min)

Mostrar `backend-integration.txt`: 195 ignorados porque não havia TEST_DATABASE_URL. Não chamar isso de aprovado. Se o ambiente de teste estiver preparado antes da aula, executar `uv run pytest tests/test_scrum_ementa_bdd.py -m integration -v -rs`, depois a suíte completa, e atualizar evidências da PR com commit e resultados. Se continuar bloqueado, explicar API + SQL + PostgreSQL e apresentar o impedimento concreto.

## 6. PR e revisão (1–2 min)

Abrir a PR no fork: conferir que base e head pertencem a pablohgs05/Case-Law. Mostrar critérios, classes/componentes, classificação, comandos e logs. Pedir a um colega revisor para conferir a entrega e registrar motivo se devolver. O autor corrige, executa novamente e atualiza a PR; o colega faz nova revisão. Não simular aprovação com a própria conta nem apresentar checklist vazio como decisão.

## Perguntas prováveis

- Unidade? No acordo validado: classes; aqui StructuredEmenta.rebuild. No frontend: componente. Funções existentes serão enquadradas com os devs na planning.
- Integração? Comunicação real entre partes: neste recorte, API, consulta e PostgreSQL com fixtures.
- Quem define critérios? Devs na planning, a partir da história explicada pelo PO. A tabela é proposta até ratificação.
- Quem corrige conflito de teste da PR? Autor da PR, com nova execução e nova revisão.
- Está tudo concluído? Unitários e frontend executados; integração e revisão humana ainda pendentes conforme evidências.
