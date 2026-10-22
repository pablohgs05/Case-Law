# Aplicação demonstrável — fatos executados em 22/10/2026

O critério técnico explícito é preservar texto e ordem das seções de StructuredEmenta.rebuild, classe utilitária. Os testes estão organizados em Dado/Quando/Então. O componente DecisionResultCard cobre ausência de trecho sem perder identificação. Critérios implementados pelo autor, com ratificação dos devs ainda pendente.

Resultados locais no código d67dee1: 4 testes da classe e 3 do componente passaram; regressão selecionada backend 105 aprovados; frontend completo 221 aprovados. Lint, formatação e tipos verificados. [Execução e logs](https://github.com/pablohgs05/Case-Law/blob/test/unitarios-fluxo-dev/documentation/testing/EXECUCAO-UNITARIA.md).

Na [PR #3 de sandbox](https://github.com/pablohgs05/Case-Law/pull/3), ed77944 introduziu troca deliberada da ordem na implementação: 4 falhas locais, saída 1. a65f469 corrigiu a classe em novo commit com testes intactos: 4 aprovações, saída 0. O CI do defeito foi cancelado; [CI da correção](https://github.com/pablohgs05/Case-Law/actions/runs/39824742488) passou. Não representa devolução humana. Nunca integrar o sandbox.

A [PR #2](https://github.com/pablohgs05/Case-Law/pull/2) nasceu da dev atual, preservando código recente dos colegas. [CI do código](https://github.com/pablohgs05/Case-Law/actions/runs/39824620373) passou; conferir Checks do head atual antes de revisar/decidir. [Auditoria de branches, proteção, DoR/DoD e alternativas](https://github.com/pablohgs05/Case-Law/blob/test/unitarios-fluxo-dev/documentation/testing/AUDITORIA-FLUXO.md). A PR #1 foi encerrada sem merge e preservada com backup; trocar só sua base traria escopo herdado de main.

Na raiz da branch test/unitarios-fluxo-dev, PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1
```

Executa classe, componente e ensaio em cópia temporária, com logs. [Roteiro da aula](https://github.com/pablohgs05/Case-Law/blob/test/unitarios-fluxo-dev/documentation/testing/APRESENTACAO.md).

Passagem humana pendente: colega acessa [PR #2](https://github.com/pablohgs05/Case-Law/pull/2) pela própria conta, valida a [ficha](https://github.com/pablohgs05/Case-Law/blob/test/unitarios-fluxo-dev/documentation/testing/PLANNING-E-REVISAO.md) com os devs e registra review do commit atual. Sem ratificação/review, não declarar DoD completo nem realizar merge. Uma devolução real exige correção, nova execução e nova revisão; não encenar rejeição.

Promoção posterior segue dev → main pelo responsável, considerando todo o conjunto de dev. Não foi aberta antecipadamente. Integração e 195 ignorados históricos continuam fora do aceite desta entrega. Nenhuma alteração em CI, proteção, ReqTrack ou original.
