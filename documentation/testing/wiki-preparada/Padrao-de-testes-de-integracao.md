# Padrão de testes de integração — Case-Law

> 🎤 **Vai conversar com o professor?** [**ABRA O GUIA VISUAL**](https://github.com/pablohgs05/Case-Law/blob/dev/documentation/testing/wiki-preparada/Guia-visual-integracao.md) — fluxograma, critérios, prova e colinha em uma página.

**Objetivo:** definir uma regra simples para que os desenvolvedores testem a comunicação entre partes do sistema, com critérios claros e evidências na Pull Request.

**Situação:** proposta de padrão para validação com o professor. Os exemplos abaixo **já existem no código** e são adequados ao projeto; não significam que a equipe original já tenha formalizado esse processo. A aplicação de testes unitários é tratada separadamente.

## 1. Fluxo mínimo (quatro etapas)

```text
PLANNING
  Devs identificam a integração afetada e o resultado esperado
       ↓
DESENVOLVIMENTO E EXECUÇÃO
  Autor prepara dependências controladas, escreve cenários BDD e executa
       ↓
PULL REQUEST → DEV
  Autor informa critério, comando, resultado, commits e logs; CI executa
       ↓
REVISÃO
  Critérios e evidências atendidos?  SIM → aprova, segue o fluxo da PR
                                    NÃO → devolve ao autor
                                          ↓ corrige, retesta e pede nova revisão
```

**Regra prática:** aplicar o padrão quando uma alteração afetar a comunicação entre módulos. Se a história não afetar uma integração, registrar brevemente a justificativa na PR, sem inventar teste desnecessário. Erro introduzido pela PR é corrigido pelo autor; falha anterior ou de infraestrutura é investigada e encaminhada ao responsável.

**Responsabilidades:** a equipe de desenvolvimento define os critérios na planning; o autor implementa e executa; o revisor confere o critério, o teste e a evidência. O CI já existente faz a reexecução automática das suítes; não é necessário criar outro pipeline.

## 2. Quais integrações serão testadas?

| Parte | Integração escolhida | Ferramentas existentes | O que se verifica |
| --- | --- | --- | --- |
| **Backend** | Endpoint FastAPI `GET /decisions` + PostgreSQL | Pytest, `TestClient` e banco real `caselaw_test` | A busca consulta o banco e retorna o conjunto correto |
| **Frontend** | Tela React + lógica de busca/paginação | Vitest e React Testing Library; resposta da API simulada | A tela transforma a resposta em quantidade, cartões e paginação corretos |

**Diferença importante:** no backend a consulta é executada de verdade no PostgreSQL de teste. No frontend, a requisição é interceptada com uma resposta controlada; testamos a integração **entre os módulos do frontend**, e não uma chamada real ao backend. Não é teste ponta a ponta (E2E).

### Backend — exemplo que já existe

Arquivo: [`backend/tests/test_search_filters.py`](https://github.com/pablohgs05/Case-Law/blob/dev/backend/tests/test_search_filters.py)  
Teste: `test_one_court_returns_only_its_decisions`

**Critério B1:** ao pesquisar "dano moral" com filtro de tribunal STJ, a API deve retornar apenas decisões daquele tribunal, com total e identificadores corretos.

- **DADO** um PostgreSQL de teste com decisões conhecidas do STJ e de outros tribunais;
- **QUANDO** o `TestClient` chamar `GET /decisions` com `q=dano moral` e `tribunal=STJ`;
- **ENTÃO** a API responde HTTP 200, `total = 2`, identificadores `2000001` e `2000002`, ambos com `court = STJ`.

Os dados são preparados por fixtures e inserções de teste. O projeto usa banco específico `caselaw_test` e rollback para não deixar alterações entre casos. **Não executar os fixtures sobre banco de produção ou desenvolvimento.**

### Frontend — exemplo que já existe

Arquivo: [`frontend/src/tests/resultsPagination.test.tsx`](https://github.com/pablohgs05/Case-Law/blob/dev/frontend/src/tests/resultsPagination.test.tsx)  
Teste: `on the first page of 45, shows 1–6 of 45, from the first page asked for`

**Critério F1:** a interface deve mostrar a quantidade e a primeira página de resultados conforme a resposta recebida, sem perder a referência do total.

- **DADO** a aplicação React com resposta **simulada** da API contendo `total = 45`;
- **QUANDO** o usuário acionar **Pesquisar**;
- **ENTÃO** a interface mostra seis cartões e a informação **"Exibindo 1–6 de 45 resultados"**, solicitando a página/bloco adequado.

O teste monta a aplicação e suas rotas e exercita a lógica real de busca e paginação, sem iniciar o backend.

## 3. Quando executar e o que registrar?

**Quando:** durante o desenvolvimento de uma história que altera essas interações, antes de solicitar aprovação da PR; repetir após cada correção relevante. O CI existente roda as suítes na PR.

**Evidência mínima na PR:** (1) integração e critério definidos; (2) arquivo/cenário testado; (3) comando e ambiente usados; (4) resultado **passou / falhou / ignorado**, com link do log e commit; (5) correção e nova execução, se necessárias.

**Passou no teste** não significa, por si só, **PR aprovada**: a revisão avalia os critérios e o impacto da alteração.

### Comandos de referência (na pasta indicada)

Backend, com `caselaw_test` preparado e `TEST_DATABASE_URL` apontando **exclusivamente** para ele:

```bash
cd backend
uv run pytest tests/test_search_filters.py -k test_one_court_returns_only_its_decisions -v
```

Frontend:

```bash
cd frontend
npm test -- src/tests/resultsPagination.test.tsx
```

Sem `TEST_DATABASE_URL`, os testes que dependem de PostgreSQL podem ser **ignorados**, e não considerados aprovados. No [CI existente](https://github.com/pablohgs05/Case-Law/blob/dev/.github/workflows/ci.yml), um serviço PostgreSQL e a variável de teste já são configurados.

## 4. Roteiro de fala (aprox. 1 minuto)

> Professor, a proposta é padronizar testes de integração para as alterações que afetam a comunicação entre partes do Case-Law.
>
> Na planning, os desenvolvedores definem a integração e os critérios. Durante o desenvolvimento, o autor prepara os dados e dependências, escreve os cenários Dado/Quando/Então e executa os testes. Na PR, registra os comandos e resultados. O revisor confere os critérios e evidências: aprova ou devolve para correção e nova execução.
>
> O padrão vale para backend e frontend. No backend, testamos a API de busca com um PostgreSQL real de teste; no frontend, a tela integrada à lógica de paginação, com uma resposta controlada da API. Os dois exemplos já têm testes no Case-Law. Queremos validar se esse é um padrão mínimo suficiente para a equipe seguir.

## 5. Se o professor perguntar

| Pergunta | Resposta curta |
| --- | --- |
| **Qual é a unidade testada?** | A **integração delimitada entre partes**, não uma classe isolada. API + PostgreSQL no backend; interface + lógica de busca no frontend. |
| **Quem define os critérios?** | Os desenvolvedores durante a planning. |
| **Quais critérios, concretamente?** | Backend: STJ → exatamente 2 decisões corretas. Frontend: 45 resultados → 6 na primeira página e faixa 1–6 de 45. |
| **Quando é feito?** | Durante o desenvolvimento, antes da revisão e novamente após correções; CI na PR. |
| **Por que não basta teste unitário?** | Porque aqui se verifica a comunicação entre elementos reais do sistema, como API + consulta SQL, ou tela + navegação + busca. |
| **É necessário subir o sistema inteiro?** | Não. O backend usa PostgreSQL de testes e `TestClient`; o frontend usa resposta de API simulada. |
| **E quando falha?** | O autor corrige o que sua PR introduziu, reexecuta e solicita nova revisão. |
| **CI verde sozinho aprova a PR?** | Não. O revisor ainda confere critérios e evidências. |

**Pergunta final para validar com o professor:** "Podemos adotar esse fluxo de quatro etapas como padrão de testes de integração dos devs, exigindo-o quando a história alterar a comunicação entre módulos, com exemplos API + PostgreSQL e interface + lógica de busca?" 

---

**Referências do fork:** [testes de banco](https://github.com/pablohgs05/Case-Law/blob/dev/backend/tests/test_search_filters.py) · [testes da interface](https://github.com/pablohgs05/Case-Law/blob/dev/frontend/src/tests/resultsPagination.test.tsx) · [fixture e isolamento](https://github.com/pablohgs05/Case-Law/blob/dev/backend/tests/conftest.py) · [CI existente](https://github.com/pablohgs05/Case-Law/blob/dev/.github/workflows/ci.yml).
