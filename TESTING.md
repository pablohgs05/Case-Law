# Testes unitários aplicados no fork

Entrega de código: [PR #2 → dev](https://github.com/pablohgs05/Case-Law/pull/2). Ensaio isolado: [PR #3](https://github.com/pablohgs05/Case-Law/pull/3). A PR #1 foi substituída porque seu head herdava alterações de main que não pertencem a esta contribuição.

Fluxo confirmado nos workflows e no histórico: contribuição → dev → main. O guard só atua em PRs para main/producao; para dev, não deve aparecer como falho nem precisa ser removido. O CI existente executa em toda PR. Promoção dev → main depende da revisão real e da decisão do responsável; não foi aberta porque incluiria outras funcionalidades ainda em dev.

## Critérios e execução

U1: classe utilitária StructuredEmenta.rebuild. Dadas seções distintas, quando reconstruir a ementa, então preservar todo o texto e a ordem cabeçalho/caso/questão/razões/dispositivo. Limites: vazio, acentos/quebra e espaços. Quatro testes isolados, sem banco ou rede.

U2: componente DecisionResultCard. Dado trecho vazio, em branco ou com quebra, quando renderizar, então exibir “Trecho indisponível.” e manter processo/tribunal. Três testes com props controladas no jsdom. O campo deliberation foi acrescentado apenas ao fixture para respeitar o contrato atual de dev.

São critérios técnicos explicitados pelo autor e implementados. Ratificação dos devs na planning e vínculos SCRUM-18/20 e SCRUM-50/55 ainda não comprovados. Não houve aceite do professor ou review humano fabricado.

Neste computador, na raiz:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1
```

O script executa 4 testes da classe, 3 do componente e repete falha/correção em cópia temporária. Salva novos logs. Para preparar outra máquina: Python 3.12+, uv e Node/npm; executar `uv sync --locked` em backend e `npm ci` em frontend. Não precisa iniciar aplicação ou banco para esta demonstração.

[Resultados e comandos](documentation/testing/EXECUCAO-UNITARIA.md) · [Roteiro oral 7–9 min](documentation/testing/APRESENTACAO.md) · [Auditoria de fluxo](documentation/testing/AUDITORIA-FLUXO.md) · [Ficha humana](documentation/testing/PLANNING-E-REVISAO.md).

Integração permanece integralmente na branch histórica test/scrum-demonstracao, sem compose ou teste novo de integração nesta PR. Os 195 ignorados anteriores continuam sem aprovação. A execução automática da suíte histórica pelo CI existente é registrada separadamente; não representa aceite da entrega de integração.
