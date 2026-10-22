# Testes unitários: processo para a equipe

A apresentação atual cobre **somente testes unitários**. [Comece pelo roteiro](documentation/testing/APRESENTACAO.md). [Integração posterior](documentation/testing/INTEGRACAO-POSTERIOR.md) tem ambiente e critérios separados.

## Base existente e limites

A [anotação do professor](https://github.com/pablohgs05/Case-Law/wiki/Fluxo-de-teste-unitario) define classes de regra de negócio, serviço e utilitárias no backend; componentes no frontend. Devs definem classes e critérios na planning; autor isola, executa e registra; outro integrante revisa. O autor resolve falhas e conflitos introduzidos na própria PR.

O [backlog da Sprint 1](documentation/sprints/sprint-1/sprint-1-backlog.md) inclui detalhe com ementa completa (prioridade 4) e cartão com trecho/fonte (prioridade 2). [Artefatos](documentation/sprints/Artefatos.md) registra SCRUM-18 (detalhe) e SCRUM-50 (resultados). SCRUM-20 e SCRUM-55 são referências usadas pelos testes anteriores: a correspondência entre essas tarefas técnicas e as histórias deve ser ratificada pela equipe. Não atribuímos uma sprint atual nem alteramos ReqTrack. Não há ata de planning, acordo da equipe ou revisão humana comprovados.

## Planning → execução → revisão

1. Na planning, devs preenchem a [ficha](documentation/testing/PLANNING-E-REVISAO.md): história existente, sprint, classe/componente, tipo, cenários e critério verificável. PO esclarece o objetivo da história. Registrar validação real e responsáveis.
2. Autor prepara entradas e substitui dependências externas quando existirem. Aqui a classe recebe dados em memória e o componente recebe props; nenhum banco ou servidor é necessário.
3. Autor escreve Dado/Quando/Então, executa os testes selecionados e a regressão pertinente, registra commit, ambiente, comando, contagem e log na PR do fork.
4. Outro integrante confere critérios da planning, classificação, isolamento, cenários e evidência do commit atual. Deve conseguir repetir os comandos.
5. Se houver falha, cenário ausente, classificação incorreta ou evidência insuficiente: **Request changes**, explicando o motivo. Autor corrige inclusive conflitos de testes que introduziu, executa novamente e registra novo commit/log.
6. O mesmo revisor ou outro integrante distinto do autor faz nova revisão. **Approve** somente com critérios obrigatórios satisfeitos. Depois segue o processo de merge da equipe. Não há garantia de bloqueio automático; CI não foi alterada.

## Recorte proposto para ratificação

| ID | Unidade e tipo | Dado / Quando / Então | Arquivo |
|---|---|---|---|
| U1 principal | `StructuredEmenta.rebuild`, classe utilitária | Dadas seções com textos distintos, quando reconstruir, então preservar cabeçalho, conteúdo e ordem exata | `backend/tests/test_scrum_ementa_bdd.py` |
| U1 limites | Mesma classe | Dado texto vazio, acentuado com quebra ou com espaços, quando reconstruir, então não perder caracteres | mesmo arquivo, 3 casos |
| U2 complementar | `DecisionResultCard`, componente | Dado trecho vazio, só espaços ou quebra, quando renderizar, então orientar “Trecho indisponível.” e identificar processo e tribunal | `frontend/src/tests/scrumCardBdd.test.tsx`, 3 casos |

U1 representa o requisito existente de ementa sem perda. U2 é proposta para ausência de trecho e precisa de aceite dos devs; não é apresentado como critério já acordado. Esses casos não comprovam toda a história. Funções e páginas presentes nas suítes históricas não são automaticamente classes/componentes aprovados pelo professor; enquadramento pendente com os devs. BDD aqui é organização do comportamento em Pytest/Vitest, sem Cucumber obrigatório.

## Preparar uma vez

Na raiz do projeto, PowerShell, com Python 3.12+, uv e Node/npm instalados:

```powershell
cd backend
uv sync --locked
cd ../frontend
npm ci
cd ..
```

Não iniciar a aplicação ou banco para os unitários. Se uv/npm não forem encontrados, corrigir a instalação/PATH antes da aula. Neste computador o ambiente Python e dependências frontend já existem; o script abaixo também usa esses caminhos diretamente.

## Executar na aula

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Apresentar-Unitarios.ps1
```

O script usa o ambiente local ou uv e procura Node no PATH; registra logs em pasta nova em `documentation/testing/evidence/unitarios/`. Interrompe se uma etapa normal falhar. Executa 4 casos da classe, 3 do componente e o ensaio de falha/correção. A falha deliberada é esperada somente dentro do ensaio.

Para executar manualmente:

```powershell
cd backend
uv run pytest tests/test_scrum_ementa_bdd.py -m unit -v
uv run python scripts/demo_test_cycle.py
cd ../frontend
npm test -- src/tests/scrumCardBdd.test.tsx
```

Antes de entregar uma mudança, rodar também `uv run pytest -m unit -q` no backend e `npm test` / `npm run typecheck` no frontend. Suíte frontend inclui páginas e utilitários além de componentes; sua contagem não é apresentada como quantidade de componentes isolados.

## Evidência mínima e conclusão

Usar o [template de PR](.github/PULL_REQUEST_TEMPLATE/testes.md): história/critério, unidade, cenário, motivo do isolamento, SHA do código testado, comandos e versões, aprovados/falhos/ignorados e logs. Resultado ignorado não é aprovação. Cobertura percentual não substitui cenário. Revisor registra decisão pela própria conta, com justificativa e nova revisão após correção.

[Resultados atuais](documentation/testing/EXECUCAO-UNITARIA.md) · [Ficha e instruções do colega](documentation/testing/PLANNING-E-REVISAO.md). A PR #1 permanece draft, sem autoaprovação. Integração está preservada em arquivo próprio e não integra a demonstração de hoje.

## Compatibilidade com DoR/DoD existentes

Artefatos.md exige subtarefas estimadas que caibam em uma pessoa, critérios testáveis e dependências identificadas antes da sprint; confirmar esses campos na planning. O DoD exige review por outro membro via PR, CI verde como condição de merge e prova de que o teste quebra ao alterar o código. O ensaio cobre essa prova técnica; testes locais verdes não concluem o DoD. Estado do CI deve ser conferido pelo responsável antes do merge, sem mudar sua configuração. Defeito fora de escopo deve ser encaminhado ao responsável para card Bug vinculado, conforme o DoD existente.
