# Testes no Case-Law — guia da Wiki

Esta Wiki reúne o padrão de testes por responsabilidade e os exemplos técnicos usados para demonstrar o processo no projeto.

## Testes de integração — padrão para validar com o professor

- **[Padrão de testes de integração](Padrao-de-testes-de-integracao)** — fluxo em quatro etapas, definição da integração, critérios BDD, backend e frontend, roteiro de fala e perguntas.
- **Backend:** API FastAPI + PostgreSQL real de teste; filtro por STJ retorna duas decisões corretas.
- **Frontend:** tela React + lógica de pesquisa/paginação com resposta de API simulada; 45 resultados e seis cartões na primeira página.
- **Decisão em validação:** confirmar com o professor se esse recorte mínimo deve ser exigido quando uma história alterar uma integração.

## Testes unitários — evidências existentes

- [Anotação do fluxo de teste unitário validado conceitualmente](Fluxo-de-teste-unitario)
- [PR #2: testes unitários integrados à dev](https://github.com/pablohgs05/Case-Law/pull/2)
- [PR #3: sandbox de defeito deliberado e correção](https://github.com/pablohgs05/Case-Law/pull/3) — não integrar
- [Aplicação demonstrável](Aplicacao-demonstravel)
- [Roteiro dos testes unitários](https://github.com/pablohgs05/Case-Law/blob/dev/documentation/testing/APRESENTACAO.md)

**Fluxo de contribuição:** branch → PR para `dev` → promoção posterior `dev → main` conforme responsáveis. Testes de unidade e integração têm escopos próprios; resultados ignorados não são aprovações. O repositório original, proteções, CI e ReqTrack não são alterados por esta documentação.
