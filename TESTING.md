# Processo de testes unitários

## Objetivo

O processo define como a equipe escolhe, escreve, revisa e aprova testes
unitários para alterações no Case-Law. Ele é aplicado durante o
desenvolvimento, antes de uma alteração ser considerada pronta para merge.

## Definição de unidade

Unidade é a menor parte do código que pode ser preparada, executada e
verificada de forma isolada. No projeto, pode ser uma função, método, classe,
serviço, transformação ou componente com comportamento próprio. O tamanho do
arquivo não define a unidade; o comportamento verificável define.

## Quem define os critérios

Os critérios não são definidos por uma única pessoa. Eles são definidos na
reunião de planejamento/refinamento pela equipe de desenvolvimento, a partir
da história, da regra de negócio e do risco da alteração.

O resultado do planejamento é uma lista objetiva:

- unidade que será coberta;
- comportamento esperado;
- cenários de sucesso;
- entradas inválidas e limites;
- dependências que precisam ser simuladas;
- evidência que será exigida para aprovar a alteração.

O responsável pelo produto apresenta o objetivo da história. Os
desenvolvedores transformam esse objetivo em critérios verificáveis e casos de
teste. O revisor da alteração verifica se os testes realmente atendem aos
critérios definidos.

Quem organiza o processo de testes não define sozinho o comportamento do
produto. A equipe de desenvolvimento define os critérios em conjunto; o autor
implementa e comprova; o revisor valida a evidência.

## Fluxo aplicado à equipe

1. **Planejamento:** a equipe define as classes, funções ou componentes que
   possuem lógica e serão cobertos.
2. **Implementação:** o desenvolvedor altera o código e cria ou atualiza os
   testes da unidade modificada.
3. **Execução local:** o desenvolvedor executa os testes e anexa o resultado à
   revisão.
4. **Revisão:** outro integrante verifica a regra, os cenários, as
   expectativas e o isolamento das dependências.
5. **Aprovação:** a alteração só é aprovada quando os critérios e os testes
   estão atendidos.
6. **Devolução:** se um teste falhar ou um critério não estiver coberto, a
   revisão é recusada/devolvida ao autor com a correção solicitada.
7. **Nova validação:** o autor corrige, executa novamente e atualiza a
   evidência da revisão.

Quem corrige é o autor da alteração que quebrou o comportamento. Se a falha
for causada por uma alteração já integrada de outro autor, o revisor registra
o defeito e a equipe encaminha a correção ao autor responsável pela mudança,
sem aprovar uma alteração quebrada.

Uma PR recusada não é descartada: ela volta ao autor com o motivo registrado.
Depois da correção, os testes são executados novamente e a nova evidência é
apresentada para revisão.

## Estrutura do teste

Os cenários seguem **Given / When / Then**:

- **Given:** contexto inicial;
- **When:** ação executada;
- **Then:** resultado esperado.

Quando a unidade possui banco, API, relógio, arquivo ou outro serviço como
dependência, a dependência é substituída por mock, fake ou simulação. O teste
verifica a unidade, não o funcionamento da dependência substituída.

## Critérios de aceitação

Um teste unitário é aceito quando:

- testa uma unidade específica;
- verifica um comportamento definido no planejamento;
- é isolado da infraestrutura externa;
- é determinístico e repetível;
- falha quando a regra é quebrada;
- tem uma expectativa clara;
- passa junto com a suíte existente;
- possui resultado registrado na revisão.

Cobertura é analisada como evidência complementar. Percentual alto não
substitui cenários relevantes e expectativas corretas.

## Aplicação existente no projeto

O processo já está aplicado no backend Python. A suíte fica em
`backend/tests`, usa PyTest e contém testes de funções puras, testes com
dependências simuladas e testes separados que exigem PostgreSQL. O marcador
`unit` identifica os testes unitários, por exemplo:

```bash
cd backend
uv run pytest -m unit -v
```

O arquivo `backend/tests/test_ementa.py` verifica isoladamente a transformação
da ementa, sem banco ou rede. O arquivo `backend/tests/test_config.py`
verifica a transformação das configurações e usa `monkeypatch` para simular o
ambiente. Esses são exemplos concretos de aplicação do processo.

## Evidências do processo

Uma alteração apresenta evidência suficiente quando registra:

- critério definido no planejamento;
- unidade escolhida;
- cenários cobertos;
- comando executado;
- resultado dos testes;
- decisão de aprovação ou devolução;
- correção realizada quando houve falha.

## Relação com DevOps

```text
Critério definido no planejamento
        ↓
Código e teste desenvolvidos
        ↓
Teste executado localmente
        ↓
Resultado anexado à revisão
        ↓
PR aprovada ou devolvida para correção
        ↓
Verificação automatizada do projeto
```

O teste unitário é a prática de qualidade. A revisão decide se o critério foi
atendido. A automação executa os comandos de validação, mas não substitui a
decisão da equipe sobre a qualidade do cenário.
