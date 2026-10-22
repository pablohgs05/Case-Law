# Apresentação unitária — 7 a 9 minutos

## Antes da aula

Preparar dependências conforme TESTING.md e ensaiar `scripts/Apresentar-Unitarios.ps1`. Abrir Wiki, TESTING.md, classe `backend/app/ementa.py`, teste `backend/tests/test_scrum_ementa_bdd.py` e PR #1. Ter outro integrante disponível para revisar pela própria conta. Se ainda não houver ratificação/revisão, apresentar como pendência real.

## 1. Explicar a regra (1 minuto)

“Hoje apresento somente unitários. A anotação do professor pede classes de negócio, serviço ou utilitárias no backend e componentes no frontend. Devs definem os critérios na planning. Escolhemos como proposta a classe utilitária que reconstrói uma ementa sem perder texto.”

Mostrar a anotação original da Wiki e o vínculo com o detalhe de decisão no backlog. “A equipe ainda precisa confirmar a ficha; não estou afirmando que a reunião já aconteceu.” Se a equipe ratificar depois, mostrar o registro real.

## 2. Mostrar o comportamento (1 minuto)

Abrir `test_rebuild_preserva_secoes_distintas`. Ementa significa resumo organizado da decisão. Dado: cabeçalho e quatro seções com textos diferentes. Quando: `rebuild()`. Então: comparar texto literal completo, sem perda nem troca de ordem. Explicar que a classe não acessa banco, rede ou API. Os três outros casos verificam vazio, acento/quebra e espaços.

## 3. Executar (2 minutos)

Na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1
```

Mostrar quatro aprovações do backend e três do componente. No frontend, abrir o teste e explicar: props controladas sem trecho; renderiza; informa “Trecho indisponível.” e mantém tribunal/processo. Renderizar no jsdom não exige abrir o sistema no navegador.

## 4. Demonstrar que o teste detecta defeito (1–2 minutos)

O mesmo script executa o ensaio: copia classe/testes para uma pasta temporária, troca a ordem de caso/questão **na classe copiada**, mantém a expectativa e exige falha. Depois restaura a classe e exige aprovação. Resultado esperado: 4 falhas deliberadas na fase quebrada; depois 4 aprovações. Não é defeito publicado nem review humano. A pasta temporária é removida; a classe real permanece intacta.

“Este vermelho prova que trocar a ordem quebra o critério. O verde após restaurar a classe comprova a correção técnica. O script não aprova a PR.”

Se uma etapa normal falhar, parar, ler o log e corrigir; não apresentar falha inesperada como ensaio.

## 5. PR e outro integrante (2 minutos)

Abrir https://github.com/pablohgs05/Case-Law/pull/1 e verificar fork nas duas pontas. Mostrar evidências e commit. Colega segue PLANNING-E-REVISAO.md: Files changed → Review changes → Request changes (se identificar problema concreto) ou Approve (se os critérios estiverem satisfeitos). Não solicitar rejeição artificial. Se devolver, autor corrige e executa novamente; o colega revisa o novo commit. Se não houver colega, mostrar campos pendentes e explicar que o fluxo técnico foi ensaiado e a decisão humana ainda falta.

## Perguntas rápidas

- Quem decide os cenários? Devs na planning, com o objetivo esclarecido pelo PO.
- Quem corrige conflitos/falhas introduzidos na PR? O autor, seguido de nova execução e revisão.
- Passar testes significa PR aprovada? Não; outro integrante precisa avaliar critérios e evidências.
- Integração? É a próxima entrega, documentada separadamente; não executar nem usar seus ignorados como aprovação nesta apresentação.
