# Aplicação demonstrável — foco unitário

A [anotação do professor](Fluxo-de-teste-unitario) permanece intacta.

Cenário principal: classe utilitária StructuredEmenta.rebuild reconstrói cabeçalho/quatro seções sem perda ou troca. Quatro testes cobrem textos distintos, vazio, acento/quebra e espaços. Componente DecisionResultCard: três casos de trecho ausente, com orientação e identificação da decisão.

[Comandos e processo](https://github.com/pablohgs05/Case-Law/blob/test/scrum-demonstracao/TESTING.md) · [Roteiro unitário](https://github.com/pablohgs05/Case-Law/blob/test/scrum-demonstracao/documentation/testing/APRESENTACAO.md) · [Evidência atual](https://github.com/pablohgs05/Case-Law/blob/test/scrum-demonstracao/documentation/testing/EXECUCAO-UNITARIA.md).

O ensaio altera a ordem na classe em cópia temporária e mantém os testes: quatro falhas deliberadas; restaura a classe e obtém quatro aprovações. Isso comprova detecção técnica e não review humano. Código real intacto.

[PR #1 no fork](https://github.com/pablohgs05/Case-Law/pull/1) preservada em draft. Ratificação da planning, vínculo das tarefas técnicas às histórias/sprint e revisão por outro integrante seguem pendentes. Usar a [ficha da equipe](https://github.com/pablohgs05/Case-Law/blob/test/scrum-demonstracao/documentation/testing/PLANNING-E-REVISAO.md). Não houve acordo ou aprovação fabricados.

[Integração posterior](https://github.com/pablohgs05/Case-Law/blob/test/scrum-demonstracao/documentation/testing/INTEGRACAO-POSTERIOR.md): teste em arquivo próprio, compose isolado preparado. Sem Docker/PostgreSQL/TEST_DATABASE_URL neste computador, ambiente não executado. Os 195 ignorados históricos não são aprovados. Fora da aula unitária.
