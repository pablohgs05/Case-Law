# Roteiro oral concreto — 7 a 9 minutos

Abrir [PR #2](https://github.com/pablohgs05/Case-Law/pull/2), [PR #3](https://github.com/pablohgs05/Case-Law/pull/3), testes focais e Wiki. Na raiz, executar o comando abaixo. Usar a branch test/unitarios-fluxo-dev; não alterar main/dev durante a aula.

## 0:00–1:00 — entrega e fluxo

“Aplicamos a demonstração unitária no fork. A contribuição está na PR #2 com destino dev, conforme o fluxo de código existente. O destino main aceita origem dev. Corrigimos o encaminhamento sem alterar o CI. A branch antiga está preservada e a PR #1 foi substituída. Ainda não integramos a contribuição: a decisão de outro integrante está pendente.”

Mostrar head/base da PR #2 e a auditoria. Não afirmar que a equipe já concordou: “Os critérios estão explícitos e os testes foram executados. A ratificação da planning está marcada como pendência porque não há registro dessa reunião.”

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

Voltar à PR #2, aba Checks e arquivos. “Aqui estão os cenários, os comandos, os commits e as evidências. O CI existente valida esta PR. Teste verde é evidência técnica; a revisão por outro integrante é uma decisão distinta.”

Mostrar o estado real dos checks do head atual. Se colega já revisou, mostrar o link e a decisão reais; sem review, dizer: “A única passagem humana pendente é um colega validar a ficha de critérios e revisar esta PR pela própria conta. Não registrei aprovação em nome dele.”

“A promoção para main passa depois por dev → main, com avaliação do conjunto que estiver em dev pelo responsável. Não abrimos essa promoção nesta demonstração porque ela incluiria outras funcionalidades.”

## 8:00–9:00 — limite da entrega

“Esta apresentação comprova o recorte unitário e a detecção de defeito. Integração está separada; os 195 ignorados do histórico não foram contados como aprovados. Não alegamos aceite do professor, planning ratificada ou DoD completo sem evidência humana.”

Se houver devolução real, mostrar o critério apontado, correção, novo commit, execução e nova revisão. Não pedir rejeição artificial para encenar o processo.
