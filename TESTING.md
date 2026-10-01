# Processo de testes do Case-Law

Este é o processo de testes aplicado pela equipe no Scrum. Ele organiza a
definição dos critérios, a escolha do tipo de teste, a execução, a revisão da
PR e o tratamento de falhas antes da alteração seguir no DevOps.

## 1. O que é uma unidade

Unidade é a menor parte do código que possui um comportamento próprio e que
pode ser preparada, executada e verificada isoladamente. No Case-Law, uma
unidade é uma função, método, classe, serviço, transformação ou componente.

O tamanho do arquivo não define a unidade. O comportamento verificável define.
Uma unidade recebe um contexto, executa uma ação e produz um resultado que o
teste consegue conferir.

## 2. Diferença entre os testes

### Teste unitário

O teste unitário verifica uma unidade isolada. Banco de dados, rede, relógio,
arquivo ou outro serviço não participa da execução real. Essas dependências
são substituídas por mocks, fakes ou simulações.

No projeto, o teste unitário cobre configurações, transformações de ementas,
regras e componentes isolados.

### Teste de integração

O teste de integração verifica a comunicação real entre partes do sistema. No
Case-Law, a API e as consultas são executadas contra um PostgreSQL de teste
real, preparado com os fixtures de `backend/tests/fixtures`.

Ele comprova comportamentos que um mock não comprova, como busca textual,
filtros, ordenação, contrato da resposta e regras SQL.

A classificação é objetiva: dependência simulada é teste unitário;
dependência real é teste de integração.

## 3. Quem define os critérios

Os critérios não são definidos por uma pessoa isolada. No Planning da história,
o Product Owner apresenta o objetivo e a equipe de desenvolvimento define em
conjunto:

1. a unidade ou integração que será coberta;
2. o tipo de teste: `unit` ou `integration`;
3. o comportamento esperado;
4. os cenários de sucesso, erro e limite;
5. as dependências que serão simuladas ou executadas de verdade;
6. o resultado exigido para aprovar a alteração.

O responsável pelo processo organiza e documenta o método. Ele não inventa
sozinho os critérios do produto. A equipe define os critérios, o autor
implementa e comprova, e o revisor valida.

## 4. Given / When / Then

Todo cenário é escrito em três partes:

- **Given (Dado):** contexto inicial, entradas e dependências preparadas;
- **When (Quando):** ação executada na unidade ou na integração;
- **Then (Então):** resultado que precisa ser verdadeiro.

Exemplo de teste unitário:

```python
def test_separa_ementa_em_secoes():
    # Given: uma ementa com seções conhecidas
    texto = "DIREITO CIVIL.\nI. CASO EM EXAME\nFatos.\nII. DECISÃO\nResultado."

    # When: a transformação é executada
    resultado = split(texto)

    # Then: as seções são identificadas corretamente
    assert resultado["caso_em_exame"] == "Fatos."
    assert resultado["decisao"] == "Resultado."
```

O exemplo prova somente a transformação. Ele não abre banco, não chama a API
e não depende de outro serviço; por isso é unitário.

## 5. Fluxo aplicado no Scrum

Unidade é a menor parte do código que possui comportamento próprio e pode ser executada e testada isoladamente

A unidade a ser testada no projeto é a classe:
Serão priorizadas para cobertura de teste os seguintes tipos:
- regra de negócio
- serviço
- utilitárias
Na reunião de planejamento são definidas quais classes serão cobertas pelos testes unitários

Criação dos casos de teste pelo dev -> isolará as classes e testará seguindo as prátcas:
- Given - o contexto inicial
- When - ação executada
- Then - verificando o resultado esperado

```text
Planning da história
        ↓
Equipe define critérios, cenários e classificação
        ↓
Autor implementa código e testes
        ↓
Autor executa testes unitários e de integração definidos
        ↓
Autor registra comandos e resultados na PR
        ↓
Revisor confere critério, classificação e evidências
        ↓
Critérios atendidos e testes aprovados?
   ┌────────────────┴────────────────┐
   │                                 │
 Sim                                Não
   │                                 │
PR aprovada                    PR devolvida ao autor
   │                                 │
Segue no fluxo DevOps           Autor corrige a alteração
                                      ↓
                               Executa os testes novamente
                                      ↓
                               Atualiza a evidência
                                      ↓
                               Nova revisão da PR
```

Uma PR com teste falhando, classificação incorreta ou evidência ausente é
devolvida. O autor da alteração corrige o problema. O revisor registra o
motivo e não corrige o código no lugar do autor.

Se o defeito pertence a uma alteração já integrada, o revisor registra o
defeito e encaminha a correção ao autor responsável por aquela alteração. Uma
alteração quebrada não é aprovada para esconder o problema.

## 6. Critérios para aprovar

O revisor aprova o teste quando ele:

- verifica a unidade ou integração definida no Planning;
- usa a classificação correta;
- cobre o comportamento esperado e os cenários definidos;
- possui Given / When / Then claros;
- é determinístico e repetível;
- possui uma expectativa que falha quando a regra é quebrada;
- executa com o comando registrado;
- apresenta resultado na PR.

Cobertura percentual é uma evidência complementar. Percentual alto não
substitui cenários relevantes nem garante qualidade sozinho.

## 7. Aplicação concreta no repositório

### Backend

O PyTest usa os marcadores `unit` e `integration`:

```bash
cd backend
uv run pytest -m unit -v
uv run pytest -m integration -v
```

O comando `unit` executa testes isolados sem banco. O comando `integration`
executa a API e as consultas contra PostgreSQL real, usando
`TEST_DATABASE_URL` e os fixtures do projeto. PostgreSQL é obrigatório para
aprovar a integração; sem essa conexão, os testes ficam não executados e não
representam aprovação.

### Frontend

O Vitest executa os componentes e as regras de busca do React/TypeScript:

```bash
cd frontend
npm test
```

Os testes do frontend executam em `jsdom` e verificam o comportamento dos
componentes de forma repetível.

## 8. Evidência obrigatória na PR

O autor registra:

1. história e critério definido no Planning;
2. unidade ou integração coberta;
3. motivo da classificação;
4. cenários Given / When / Then;
5. comando executado;
6. resultado obtido;
7. decisão do revisor;
8. correção e novo resultado após uma devolução.

## 9. O que precisa ser definido pela equipe

Antes de começar o código, a equipe deve preencher estas decisões para cada
história:

| Decisão | Pergunta prática | Exemplo |
|---|---|---|
| Critério | O que precisa funcionar para a história ser aceita? | A busca deve devolver somente decisões do tribunal escolhido. |
| Cenário | Qual entrada e resultado serão verificados? | Dado um tribunal com decisões, quando pesquisar, então só ele aparece. |
| Tipo | O teste usa dependência simulada ou real? | Regra de filtro com banco real: `integration`. |
| Comando | Como qualquer integrante repete a verificação? | `uv run pytest -m integration -v`. |
| Evidência | Que resultado será anexado à PR? | Saída do comando e quantidade de testes aprovados. |
| Responsável | Quem implementa e quem revisa? | Autor executa; outro integrante confere e aprova. |

Você, no papel de DevOps, organiza essas informações e verifica se elas são
repetíveis. A equipe de desenvolvimento define o comportamento da história;
você não precisa inventar sozinho os critérios do produto.

### Exemplo concreto: filtro por tribunal

Suponha que a história seja: **“Como analista, quero filtrar decisões por
tribunal.”** O critério de aceitação pode ser escrito assim:

> Dado que existem decisões do TJDFT e do STJ, quando o usuário selecionar
> TJDFT, então a API deve retornar somente decisões do TJDFT, informar a
> quantidade correta e não retornar decisões do STJ.

Esse critério gera os cenários:

1. **Sucesso:** selecionar TJDFT retorna apenas TJDFT.
2. **Vazio:** selecionar um tribunal sem decisões retorna uma lista vazia, sem
   erro.
3. **Combinação:** selecionar dois tribunais retorna a união dos dois.
4. **Limite/erro:** informar um tribunal inexistente não causa erro interno.

O primeiro teste pode ser unitário se usar uma base falsa preparada pelo teste.
Ele verifica a regra de resposta sem depender do PostgreSQL. O teste é de
integração quando executa a API com PostgreSQL real e consulta as tabelas e os
índices verdadeiros. Os dois tipos podem existir para a mesma história:
unitário para feedback rápido e integração para confirmar que as partes
funcionam juntas.

### Respostas curtas para perguntas do professor

**“Quais são os critérios?”**

São as condições que precisam ser verdadeiras para aceitar a história. Neste
exemplo: filtrar pelo tribunal certo, retornar a quantidade certa, tratar lista
vazia e não quebrar com tribunal inexistente.

**“O que é integração?”**

É quando o teste não simula uma parte importante: ele coloca a API e o
PostgreSQL real para trabalhar juntos e verifica o resultado da comunicação.

**“Qual é a diferença para unitário?”**

Unitário testa uma parte isolada, normalmente com dados falsos ou mocks.
Integração testa a comunicação real entre partes, como API, consulta SQL e
PostgreSQL.

**“Quem decide o critério?”**

O Product Owner explica o valor da história e a equipe transforma isso em
condições verificáveis. O DevOps organiza o comando, a evidência e a execução
no CI; não decide sozinho a regra do produto.

**“Como você prova que foi aplicado?”**

Mostro o cenário, o teste classificado, o comando executado, o resultado na PR
e o CI repetindo a verificação. Se falhar, a PR volta para correção.

## 10. Relação com DevOps

O Scrum fornece a história e os critérios. O processo de testes transforma
esses critérios em verificações repetíveis. A PR concentra o código, os
testes, os resultados e a decisão de revisão. O CI executa automaticamente as
suítes e impede o avanço de uma alteração que não atende aos critérios.

Portanto, a entrega não é apenas uma ferramenta. A entrega é o fluxo aplicado:
critério definido, teste classificado, código testado, evidência registrada,
PR revisada, correção realizada quando necessário e alteração aprovada antes
de continuar no DevOps.

## 10. Roteiro curto para apresentar

1. **Contexto:** “A equipe está desenvolvendo a API; meu trabalho é organizar
   como o teste entra no fluxo de DevOps.”
2. **Decisão:** “No Planning, a equipe define o critério, o cenário e se o
   teste será unitário ou de integração.”
3. **Execução:** “O autor implementa, executa o comando e registra a evidência
   na PR.”
4. **Revisão:** “Outro integrante confere a classificação, os cenários e o
   resultado. Se falhar, a PR volta para correção.”
5. **Automação:** “O CI repete os comandos e impede o avanço quando os
   critérios não são atendidos.”

Uma frase para diferenciar os tipos: **unitário testa uma parte isolada;
integração testa partes trabalhando com uma dependência real**. Neste projeto,
o PostgreSQL real é o principal exemplo de integração.

## 11. Ferramentas

- **PyTest:** execução dos testes do backend Python;
- **Vitest:** execução dos testes do frontend React/TypeScript;
- **unittest.mock, mocks e fakes:** isolamento de dependências nos testes
  unitários;
- **monkeypatch:** simulação de variáveis de ambiente e configurações;
- **PostgreSQL:** dependência real usada nos testes de integração;
- **fixtures:** dados controlados usados para preparar o banco de teste;
- **Coverage Gutters:** visualização da cobertura durante o desenvolvimento;
- **CI:** execução automatizada dos comandos já definidos pelo processo.

## 12. Fala completa para a apresentação

> “No Planning, o Product Owner apresenta a história e a equipe define os
> critérios, os cenários e o tipo de teste. Unidade é a menor parte do código
> com comportamento próprio que conseguimos verificar isoladamente. No teste
> unitário, banco e serviços são simulados. No teste de integração, a API e o
> PostgreSQL real trabalham juntos. O autor implementa, executa e registra a
> evidência na PR. Outro integrante revisa. Teste aprovado e critério atendido
> liberam a PR. Falha, classificação errada ou evidência ausente devolvem a PR
> ao autor, que corrige, executa novamente e envia para nova revisão. Depois da
> aprovação, a alteração segue para o DevOps. Esse é o processo aplicado no
> Scrum, não apenas uma lista de ferramentas.”
