# Roteiro oral concreto — 7 a 9 minutos

**Usar a branch `dev` atualizada do fork, após obter localmente os commits mais recentes.** Abrir [PR #2](https://github.com/pablohgs05/Case-Law/pull/2), [PR #3](https://github.com/pablohgs05/Case-Law/pull/3), testes focais e Wiki. Na raiz, executar o comando abaixo. Usar a branch test/unitarios-fluxo-dev; não alterar main/dev durante a aula.

> **Estado confirmado em 22/10/2026 — fork individual:** a [PR #2](https://github.com/pablohgs05/Case-Law/pull/2) foi integrada à `dev` do fork no commit [`56a664f`](https://github.com/pablohgs05/Case-Law/commit/56a664fbac0264638af04070cbc16b9d05f7ae4a), após CI backend/frontend aprovado e verificação técnica assistida por IA registrada na PR. O autor é o único colaborador do fork. **Não houve revisão humana independente, ratificação de planning pelos devs nem aprovação do professor.** A revisão por colega permanece um requisito do processo da equipe original, demonstrado/documentado, **não uma etapa executada neste fork**. A [PR #3](https://github.com/pablohgs05/Case-Law/pull/3) é somente sandbox e não deve ser integrada. Nenhum merge em `main` ou no repositório original.

## 0:00–1:00 — entrega e fluxo

“Aplicamos o recorte de testes unitários no nosso fork. A PR #2 foi destinada a dev, recebeu CI aprovado e foi integrada à dev do fork em 22/10/2026, commit 56a664f. A revisão técnica foi assistida por IA e registrada; não houve segundo desenvolvedor para revisar, pois este fork é individual. O fluxo padrão da equipe prevê revisão independente, que está documentada mas não foi executada aqui.”

Mostrar head/base da PR #2 e a auditoria. Não afirmar que a equipe já concordou: “Os critérios técnicos foram explicitados e os testes executados. A ratificação por desenvolvedores em planning não ocorreu neste fork individual e não a apresentamos como fato.”

## 1:00–2:00 — critério e Dado/Quando/Então

“Ementa é o resumo estruturado da decisão. O critério técnico é reconstruir sem perder texto nem mudar a ordem. Dado cabeçalho e quatro seções distintas; quando rebuild é chamado; então o resultado deve ser exatamente o texto esperado.”

Abrir test_rebuild_preserva_secoes_distintas. Mostrar entrada e expectativa literal independente. “A classe é utilitária e recebe dados em memória; não usa banco ou API. Os demais casos cobrem vazio, acentos/quebra e espaços.”

## 2:00–4:00 — executar o que funciona

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1
```

“Executamos quatro testes da classe e três do componente. No cartão, dado trecho inutilizável, quando renderizamos, então aparece Trecho indisponível e a identificação continua visível. A renderização acontece no ambiente de teste; não precisamos abrir a aplicação.”

Esperar a saída real. Se ocorrer falha inesperada, interromper e ler o log; não chamá-la de ensaio. O script também executa o ensaio temporário e grava logs em nova pasta.

## 4:00–6:00 — falha e correção com commits

Na PR #3, abrir Commits: ed77944 e a65f469. “Este é um defeito deliberado de demonstração: inverti caso e questão só na branch sandbox. Os quatro testes falharam. Corrigi a implementação em outro commit, mantendo os testes, e os quatro passaram. Os logs registram os dois SHAs. O defeito não entrou em main, dev ou na contribuição unitária.”

Mostrar os dois logs em evidence/fluxo. Distinguir execução local de conclusão de cada run do CI pelo status exibido no GitHub. “O ensaio local repetido agora usa uma cópia temporária. A PR de sandbox preserva a mesma prova no histórico e não deve ser integrada.”

## 6:00–8:00 — evidência, revisão e decisão

Voltar à PR #2, aba Checks e arquivos. “Aqui estão cenários, comandos, commits, evidências, CI aprovado e merge da PR #2 na dev do fork. Registrei uma análise assistida por IA; em trabalho de equipe, a avaliação e aprovação por outro integrante seria uma etapa adicional, que não aconteceu neste fork individual.”

Mostrar o estado real dos checks do head atual. Se colega já revisou, mostrar o link e a decisão reais; sem review, dizer: “No fork individual, não houve revisão por outro dev. O registro demonstra o procedimento que o time deve seguir quando há vários integrantes, sem inventar aprovação.”

“Depois da integração em dev, o fluxo do projeto promove dev para main sob decisão do responsável. Não promovemos agora porque isso incluiria outras funcionalidades.”

## 8:00–9:00 — limite da entrega

“Esta apresentação comprova os testes unitários executados, a capacidade de detectar o defeito de sandbox e a contribuição integrada à dev do fork. Testes de integração continuam fora desta apresentação. Não houve revisão humana independente, ratificação de planning ou aceite do professor; logo não alegamos cumprimento integral do DoD da equipe original.”

Se houver devolução real, mostrar o critério apontado, correção, novo commit, execução e nova revisão. Não pedir rejeição artificial para encenar o processo.
