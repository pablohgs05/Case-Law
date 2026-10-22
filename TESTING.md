# Processo de testes do Case-Law

Escopo desta entrega: testes unitários e de integração, evidências e revisão no fork [pablohgs05/Case-Law](https://github.com/pablohgs05/Case-Law). CI e ReqTrack pertencem a outros responsáveis; este material não afirma que exista bloqueio automático de merge.

## Acordo validado e aplicação no código

A anotação original está na [Wiki: Fluxo de teste unitário](https://github.com/pablohgs05/Case-Law/wiki/Fluxo-de-teste-unitario). Na planning, os devs definem critérios e classes, priorizando regra de negócio, serviço e utilitárias. O dev isola a unidade, usa Dado/Quando/Então e registra comandos/resultados na PR. Outro integrante revisa. Se houver falha, critério não atendido ou evidência ausente, devolve ao autor, que corrige, executa novamente e pede nova revisão. Conflitos de testes introduzidos na PR são responsabilidade do autor. No frontend, a unidade é o componente.

O backend atual usa funções e classes. Para demonstrar literalmente uma classe existente, esta entrega testa `StructuredEmenta.rebuild`, utilitária de `backend/app/ementa.py`. As funções existentes continuam cobertas; não foram transformadas artificialmente em classes. O enquadramento das funções no acordo deve ser confirmado na próxima planning.

Unitário verifica comportamento isolado; mocks não demonstram que SQL funciona. Integração verifica partes reais trabalhando juntas. Aqui o recorte demonstrado é API + consulta + PostgreSQL real. Os marcadores históricos do projeto incluem alguns testes HTTP sem banco em `unit`; uma chamada HTTP simulada sozinha não prova integração com PostgreSQL. Testes de páginas com API simulada também não provam integração real frontend/backend.

## Planning demonstrativa — proposta, não reunião realizada

Histórias existentes usadas como referência: SCRUM-20 (ementa estruturada) e SCRUM-55 (cartão). Não foram criados requisitos nem alterados registros no ReqTrack. A equipe ainda deve ratificar cenários, sprint, autor e revisor.

| Critério proposto | Unidade / classificação | Dado / Quando / Então | Teste |
|---|---|---|---|
| C1: reconstruir sem perda nem troca de ordem | Classe utilitária `StructuredEmenta`, método `rebuild`; unitário sem dependência externa | Dadas quatro seções e cabeçalho com vazio, acento/quebra ou espaços, quando reconstruir, então manter todos os caracteres na ordem | `backend/tests/test_scrum_ementa_bdd.py::test_rebuild_preserva_texto_e_ordem_das_secoes` (3 casos) |
| C2: devolver todas as seções no detalhe | API `/decisions/tjdft-jurisdf/1000004` + PostgreSQL; integração | Dado fixture estruturado real, quando abrir detalhe, então HTTP 200, cinco campos preenchidos e textos presentes na ementa completa | `backend/tests/test_scrum_ementa_bdd.py::test_api_preserva_todas_as_secoes_da_ementa` |
| C3: orientar quando não há trecho | Componente `DecisionResultCard`; unitário em jsdom, props controladas | Dado trecho vazio, espaços ou quebra de linha, quando renderizar, então mostrar “Trecho indisponível.” e identificar processo/tribunal | `frontend/src/tests/scrumCardBdd.test.tsx` (3 casos) |

Sucesso, erro e limites adicionais já têm exemplos nas suítes existentes: `test_ementa.py` cobre ementa ausente/incompleta; `test_detail.py` cobre decisão inexistente/404; `officialLink.test.tsx` cobre fonte indisponível. A equipe escolhe na planning quais são obrigatórios por história.

## Executar e reunir evidências

Backend, a partir da raiz:

```powershell
cd backend
uv sync --locked
uv run pytest -m unit -v
uv run pytest -m integration -v -rs
uv run python scripts/demo_test_cycle.py
```

Frontend, a partir da raiz em outro terminal:

```powershell
cd frontend
npm ci
npm test
npm run typecheck
```

O ensaio `demo_test_cycle.py` usa somente uma cópia temporária do teste. Introduz expectativa errada, exige código de saída 1, restaura a expectativa original e exige código 0. Mostra três falhas seguidas de três aprovações sem editar código de produção. É demonstração técnica: não constitui defeito real, devolução humana ou aprovação de PR.

### Integração: ambiente necessário

Nesta execução faltam `TEST_DATABASE_URL`, Docker e PostgreSQL acessíveis pelos comandos locais. Os 195 testes de integração foram ignorados. Integração está **pendente**, apesar de pytest retornar código 0 em uma suíte inteiramente ignorada.

Em uma máquina com Docker, usar o PostgreSQL/pgvector do compose existente e criar um banco **exclusivo para testes**. Os fixtures apagam/recriam o schema `core`; não usar banco de desenvolvimento com dados úteis nem produção.

```powershell
# Na raiz, se o serviço de desenvolvimento ainda não estiver iniciado:
docker compose up -d postgres
# Criar uma vez; ajustar usuário se a configuração local for diferente:
docker compose exec postgres createdb -U postgres caselaw_test
cd backend
# Exemplo para os valores padrão do compose; adaptar localmente sem publicar segredos:
$env:TEST_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/caselaw_test'
uv run pytest -m integration -v -rs
```

O banco deve oferecer `pg_trgm`, `unaccent` e `vector`. O fixture `prepared_database` prepara tabelas e dados automaticamente. Recusar aprovação se houver falhas, erros ou cenários obrigatórios ignorados; conferir os números, não apenas o código de saída.

## Fluxo de revisão na PR

1. Devs registram história, sprint, critérios, classes/componentes, cenários e classificação na planning.
2. Autor implementa, isola e executa os testes definidos.
3. Autor abre PR **dentro do fork**, usando o [modelo de testes](.github/PULL_REQUEST_TEMPLATE/testes.md), com commit testado, comandos, ambiente, contagens e logs.
4. Revisor distinto confere critérios, classificação, isolamento, cenários e evidências.
5. Critério não atendido, falha ou evidência incompleta: revisor registra motivo e solicita alterações. Autor resolve inclusive conflitos dos testes que introduziu, executa novamente e atualiza os logs vinculados ao novo commit.
6. Revisor confere a correção e a nova execução. Somente aprova quando os critérios obrigatórios estiverem atendidos; depois segue o processo da equipe.

A revisão humana continua pendente nesta entrega. O autor não pode aprovar sua própria PR. O ensaio não substitui essa etapa nem a execução real da integração.

## Apresentação e registro

- [Roteiro de 6–8 minutos](documentation/testing/APRESENTACAO.md)
- [Execução e bloqueios de 22/10/2026](documentation/testing/EVIDENCIAS.md)
- [Logs](documentation/testing/evidence/)
