# Auditoria e decisão de encaminhamento — 22/10/2026

## Fontes conferidas

- Fork main: d6cfb771a31fd4585163f31fe19689243797b87b; dev: 5eb90ab070d6d27c230d96913643fd4e1c82bbee.
- PR #1: test/scrum-demonstracao aebdbb679d26369a8bf5cab0e17c4ac8f58a94fa → main. CI passou, guard falhou por origem diferente de dev.
- `.github/workflows/ci.yml`: pull_request em qualquer base; push em dev/main/producao. Backend com PostgreSQL de CI; frontend com testes, lint, formatação e tipos. Em dev o banco é caselaw_test; em main era caselaw. Nenhum workflow editado.
- `.github/workflows/guard-protected-branches.yml`: main só aceita dev na versão de main. Na versão de dev há exceção para docs/ → main. Como esta contribuição inclui testes/código de ensaio, a exceção documental não se aplica. Ambas exigem dev para producao.
- API autenticada do fork: rulesets vazio; main/dev protected=false, required_status_checks enforcement_level=off; endpoints de proteção retornaram 404. O workflow chamado Guard não comprova proteção administrativa. Nenhuma proteção criada/alterada.
- [DoR/DoD existentes](https://github.com/pablohgs05/Case-Law/blob/d6cfb771a31fd4585163f31fe19689243797b87b/documentation/sprints/Artefatos.md): critérios testáveis, subtarefas/horas, revisão por outro membro, CI verde e prova de quebra. Documento está em main; não foi copiado para dev como se fosse nova mudança.
- Leitura do original: PRs [#105](https://github.com/Praxis-Fatec/Case-Law/pull/105), [#101](https://github.com/Praxis-Fatec/Case-Law/pull/101) e #97 são feat/ → dev; [#92](https://github.com/Praxis-Fatec/Case-Law/pull/92) é dev → main. PRs documentais #98–100 foram para main. Histórico não implica aprovação automática da presente entrega. Nenhuma escrita no original.

## Comparação das alternativas

| Alternativa | Impacto | Decisão |
|---|---|---|
| Manter #1 → main | Guard rejeita test/; pula integração em dev | Substituída |
| Só trocar base de #1 para dev | Comparação de ancestral comum traz 65 caminhos, incluindo README, modelo de banco e artefatos de outros commits; mistura escopos | Rejeitada |
| Trocar head de #1 para dev | GitHub não permite trocar head; mover dev exigiria integração prévia e incluiria outras funcionalidades | Rejeitada |
| Copiar main inteira sobre dev | Poderia regredir funcionalidades recentes e workflows diferentes | Rejeitada |
| Branch nova da dev + seleção unitária | Preserva produção, workflows, dependências e trabalho dos colegas | PR #2 |

A PR #2 acrescenta testes focais, ensaio, comando de apresentação, marcador unit e documentação/evidência própria. Não inclui classificações históricas, alteração de decisionDetail.test.tsx, README do produto, modelo de banco, template global de PR ou integração. Código app/ e componentes/ idêntico à dev.

## Preservação

Backup local/remoto `backup/unitarios-antes-adequacao-20261022` aponta a aebdbb6. Branch test/scrum-demonstracao e seus logs/integração continuam preservados. Nenhum reset, force-push, merge ou exclusão de branch. main/dev mantêm os SHAs acima. ReqTrack não alterado. upstream push permanece DISABLED. Wiki original do professor preservada.

## Estado do ciclo

Critério explicitado → cenários BDD → testes executados → defeito deliberado no sandbox ed77944 → quatro falhas → correção em novo commit a65f469 → quatro aprovações → evidências na PR. Planejamento ratificado, revisão por colega e decisão de integração ainda dependem de pessoas reais. Sem isso, o ciclo técnico está demonstrado e o DoD humano continua aberto.
