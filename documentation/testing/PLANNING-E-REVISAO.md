# Ficha de planning e revisão — preencher com a equipe

Status do processo da equipe: **critérios propostos; ratificação e revisão humana independentes não realizadas neste fork individual**. A PR #2 já foi integrada tecnicamente à `dev` do fork em 22/10/2026 com CI aprovado e checagem assistida por IA. Este arquivo facilita o registro e não comprova uma reunião. Não mudar ReqTrack sem o responsável. O backlog já prioriza resultados com trecho e detalhe completo; confirmar vínculos SCRUM-18/20 e SCRUM-50/55 antes de registrar como tarefas acordadas.

> **Estado confirmado em 22/10/2026 — fork individual:** a [PR #2](https://github.com/pablohgs05/Case-Law/pull/2) foi integrada à `dev` do fork no commit [`56a664f`](https://github.com/pablohgs05/Case-Law/commit/56a664fbac0264638af04070cbc16b9d05f7ae4a), após CI backend/frontend aprovado e verificação técnica assistida por IA registrada na PR. O autor é o único colaborador do fork. **Não houve revisão humana independente, ratificação de planning pelos devs nem aprovação do professor.** A revisão por colega permanece um requisito do processo da equipe original, demonstrado/documentado, **não uma etapa executada neste fork**. A [PR #3](https://github.com/pablohgs05/Case-Law/pull/3) é somente sandbox e não deve ser integrada. Nenhum merge em `main` ou no repositório original.

## Registro esperado em um desenvolvimento de equipe (modelo)

- Data e link/ata real: pendente
- História e tarefa técnica existentes: pendente de confirmação
- Subtarefa, estimativa em horas e responsável conforme DoR: pendentes
- Sprint vigente: pendente (Sprint 1 é referência documental, não atribuição atual)
- Autor: pablohgs05; confirmar integrante responsável pela tarefa
- Revisor distinto, com acesso ao fork: a definir
- Classe/tipo ou componente: proposta U1 StructuredEmenta/rebuild utilitária; U2 DecisionResultCard
- Critérios e cenários: U1 preservação integral e ordem, vazio/acento/espaços; U2 fallback sem trecho
- Confirmar se esses cenários bastam ou quais sucesso/erro/limite adicionais são obrigatórios: pendente
- Dependências e isolamento: U1 memória; U2 props/jsdom; sem banco/rede
- Confirmação explícita dos devs (nomes, data, referência): pendente

## Mínimo para solicitar revisão

Critérios registrados; teste verifica resultado observável; nenhuma falha inesperada; nenhum cenário obrigatório ignorado; regressão pertinente executada; SHA, comandos, versões e logs; nenhuma credencial. Falha esperada do ensaio deve ser rotulada separadamente. Não declarar a história inteira pronta só por esses testes.

## O que o colega faz no GitHub

1. Entrar com sua própria conta e abrir a PR #2 **do fork pablohgs05/Case-Law**.
2. Confirmar critério da planning e olhar Files changed. Ler classe, testes e logs; repetir comandos de TESTING.md no commit da PR, sem usar produção.
3. Conferir se o teste realmente falha ao quebrar a regra (ensaio), isolamento, nomes, limites e resultados do commit atual.
4. Em Review changes, registrar decisão real. Se não tiver permissão para aprovar/requisitar alterações formalmente, registrar comentário identificado e pedir ao dono do fork ajuste de acesso; comentário não equivale automaticamente a aprovação formal.
5. Problema concreto: Request changes e descrever critério afetado, arquivo, comando e resultado esperado. Sem problema e requisitos satisfeitos: Approve com justificativa. Autor não revisa a própria PR como outro integrante.
6. Após devolução, verificar novo commit/log e fazer nova revisão; aprovação antiga não cobre automaticamente alteração posterior.

## Modelos para o revisor preencher (não são reviews realizados)

Devolução: “Critério __ não atendido no commit __. Executei __ e observei __. Esperado __. Solicito correção e nova evidência.”

Aprovação: “Revisei o commit __, critérios __, isolamento __ e executei __ com __ aprovados, __ falhos, __ ignorados. Critérios obrigatórios atendidos. Aprovo este recorte unitário.”

## Registro após correção

| Etapa | Pessoa real | Commit | Comando/log | Decisão/motivo e link |
|---|---|---|---|---|
| Execução do autor | pablohgs05 (execução assistida) | ver evidência | ver evidência | técnica; não é review |
| Primeira revisão | pendente | pendente | pendente | pendente |
| Correção e nova execução, se necessária | pendente | pendente | pendente | pendente |
| Nova revisão, se necessária | pendente | pendente | pendente | pendente |

Integração tem ficha/aceite próprios na entrega posterior. Não condicionar a demonstração unitária a banco, nem afirmar integração aprovada.

Antes do merge, conferir também CI verde no head atual conforme DoD do time. CI não alterado; conferir a aba Checks da PR #2.

## Quando a equipe original aplicar este modelo

Em futuros trabalhos **com vários desenvolvedores**, o colega poderá usar uma nova PR de contribuição para validar os critérios e vínculos da ficha e registrar review por conta distinta antes do merge. A PR #2 do **fork pessoal** já foi integrada, com checagem técnica de IA registrada, sem se passar por aprovação de equipe. Não retroagir aprovação inventada nem alterar o histórico para simular processo.
