# Processo de testes do Case-Law

Este processo classifica e revisa os testes unitários e de integração usados
pela equipe no fluxo de desenvolvimento. A classificação é definida no
planejamento ou no início de cada sprint, junto com os critérios da história.

## 1. Definição de unidade e de integração

**Teste unitário** verifica uma unidade isolada: função, método, classe,
serviço, transformação ou componente. Dependências externas, como banco,
rede, relógio e arquivos, são substituídas por mocks, fakes ou simulações.

**Teste de integração** verifica a comunicação real entre partes do sistema.
No Case-Law, os testes de integração do backend executam a API e as consultas
contra um PostgreSQL de teste preparado com os fixtures do projeto. Eles
confirmam o comportamento que não pode ser provado por um mock, como busca
textual, filtros, ordenação, contratos de resposta e regras SQL.

O tamanho do arquivo não define a classificação. O que define é a
dependência exercitada e o objetivo do cenário.

## 2. Quem define os critérios

Na reunião de planejamento/refinamento, o responsável pelo produto apresenta o
objetivo da história e a equipe de desenvolvimento define em conjunto:

- a unidade ou integração alterada;
- o tipo de teste: `unit` ou `integration`;
- os cenários de sucesso, erro e limite;
- as dependências que devem ser simuladas ou reais;
- a evidência exigida para aprovar a alteração.

O autor implementa o código e os testes. Outro integrante revisa a
classificação, os cenários e os resultados. O responsável pelo processo
organiza o método, mas não decide sozinho o comportamento do produto.

## 3. Fluxo aplicado em cada sprint

```text
Planejamento define critério e classifica o teste
                     ↓
Autor implementa código e teste
                     ↓
Executa unitários isolados
                     ↓
Executa integrações com PostgreSQL, quando o critério exige
                     ↓
Registra comandos e resultados na PR
                     ↓
Revisor confere classificação, cobertura e evidência
                     ↓
              Critérios atendidos?
                /              \
              Sim               Não
              ↓                 ↓
        PR aprovada       PR devolvida ao autor
              ↓                 ↓
      segue no DevOps       autor corrige
                                  ↓
                         executa novamente e atualiza
                         a evidência para nova revisão
```

Se a falha foi causada pela alteração da PR, o autor corrige. Se o defeito
pertence a uma alteração já integrada, o revisor registra o problema e ele é
encaminhado ao autor responsável. Uma PR com teste falhando não é aprovada.

## 4. Aplicação real no repositório

### Backend

O PyTest classifica os testes com marcadores:

- `unit`: configuração, transformação de ementas, regras e endpoints isolados
  com dependências simuladas;
- `integration`: API e consultas que usam PostgreSQL real. Esses testes usam
  `TEST_DATABASE_URL` e os fixtures em `backend/tests/fixtures`.

Comandos usados na revisão:

```bash
cd backend
uv run pytest -m unit -v
uv run pytest -m integration -v
```

O primeiro comando não precisa de banco. O segundo exige um PostgreSQL de
teste e prepara o schema pelos fixtures. Sem `TEST_DATABASE_URL`, os testes de
integração ficam explicitamente marcados como não executados; isso não é
evidência de integração aprovada.

### Frontend

Os componentes e regras de busca do React/TypeScript são executados pelo
Vitest em ambiente `jsdom`:

```bash
cd frontend
npm test
```

Esses testes verificam componentes e regras do frontend de forma isolada. A
classificação de integração do processo fica reservada aos cenários que
exercitam uma dependência real do sistema, como o PostgreSQL do backend.

## 5. Critério de aprovação e evidência

Uma alteração é aprovada quando registra:

1. critério definido no planejamento;
2. unidade ou integração coberta;
3. motivo da classificação;
4. cenários Given / When / Then;
5. comando executado;
6. resultado obtido;
7. decisão do revisor;
8. correção e nova execução, quando a PR foi devolvida.

Cobertura percentual é evidência complementar. Ela não substitui cenários
relevantes nem garante, sozinha, qualidade.

## 6. Relação com DevOps

O processo entrega ao restante do DevOps testes classificados, comandos
repetíveis e resultados verificáveis. A etapa de CI pode executar exatamente
esses comandos e bloquear a progressão de uma alteração quando os critérios
não forem atendidos. A implementação deste documento é o contrato de testes;
o CI é a automação que o consome.
