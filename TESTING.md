# Processo de testes do Case-Law

Este é o processo de testes usado pela equipe no Scrum. A classificação, os
cenários e a evidência são definidos no planejamento da história, registrados
no início da sprint e revisados na PR.

## 1. Classificação definida pela equipe

**Teste unitário** verifica uma função, método, classe, serviço, transformação
ou componente isolado. Banco, rede, relógio e arquivos são substituídos por
mocks, fakes ou simulações.

**Teste de integração** verifica a comunicação real entre partes do sistema.
No Case-Law, ele executa a API e as consultas contra PostgreSQL de teste, com
os fixtures de `backend/tests/fixtures`.

O planejamento registra a classificação, os cenários de sucesso, erro e
limite, as dependências simuladas ou reais e o resultado exigido para
aprovação. O Product Owner apresenta o objetivo da história; os
desenvolvedores definem os critérios; o autor implementa; outro integrante
revisa.

## 2. Fluxo Scrum aplicado

```text
Planning da história
        ↓
Equipe registra critérios e classificação
        ↓
Autor desenvolve código e testes
        ↓
Autor executa unitários e integrações definidas
        ↓
Autor registra comando e resultado na PR
        ↓
Revisor confere critério, classificação e evidência
        ↓
Critérios atendidos?
   ┌───────────────┴───────────────┐
   │                               │
 Sim                              Não
   │                               │
PR aprovada                  PR devolvida ao autor
   │                               │
Segue no fluxo DevOps         Autor corrige e executa
                              novamente os testes
                                      ↓
                               Nova revisão da PR
```

Uma PR com teste falhando ou sem evidência é devolvida. O autor da alteração
corrige a falha. O revisor registra a decisão e não corrige o código no lugar
do autor.

## 3. Implementação no repositório

### Backend

O PyTest usa os marcadores `unit` e `integration`:

```bash
cd backend
uv run pytest -m unit -v
uv run pytest -m integration -v
```

`unit` executa configurações, transformações, regras e componentes isolados.
`integration` executa a API e as consultas contra PostgreSQL real, usando
`TEST_DATABASE_URL` e os fixtures do projeto. PostgreSQL é obrigatório para a
execução de integração; testes sem essa conexão ficam marcados como não
executados e não geram aprovação.

### Frontend

O Vitest executa os componentes e as regras de busca do React/TypeScript:

```bash
cd frontend
npm test
```

## 4. Evidência exigida na PR

O autor registra:

1. história e critério definido no Planning;
2. unidade ou integração coberta;
3. motivo da classificação;
4. cenários Given / When / Then;
5. comando executado;
6. resultado;
7. decisão do revisor;
8. correção e novo resultado após devolução.

Cobertura percentual é evidência complementar. Ela não substitui cenários
relevantes nem expectativas corretas.

## 5. Relação com DevOps

O processo transforma o critério do Scrum em teste repetível e evidência de
qualidade. A revisão da PR impede a progressão de uma alteração sem critério
atendido. O CI executa a suíte automatizada do backend e do frontend; o
processo define o que deve ser testado e como o resultado é aceito.

## 6. Fala para a apresentação

> “No Planning, o Product Owner apresenta a história e a equipe de
> desenvolvimento define os critérios, os cenários e a classificação. Teste
> unitário verifica uma unidade isolada com dependências simuladas. Teste de
> integração verifica a API usando PostgreSQL real. O autor implementa e
> executa os testes, registra o resultado na PR e outro integrante revisa.
> Critério atendido aprova a PR. Falha ou ausência de evidência devolve a PR ao
> autor, que corrige, executa novamente e envia para nova revisão. Esse é o
> ponto em que o processo Scrum entrega uma alteração validada ao fluxo DevOps.”
