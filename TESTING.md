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

## 9. Relação com DevOps

O Scrum fornece a história e os critérios. O processo de testes transforma
esses critérios em verificações repetíveis. A PR concentra o código, os
testes, os resultados e a decisão de revisão. O CI executa automaticamente as
suítes e impede o avanço de uma alteração que não atende aos critérios.

Portanto, a entrega não é apenas uma ferramenta. A entrega é o fluxo aplicado:
critério definido, teste classificado, código testado, evidência registrada,
PR revisada, correção realizada quando necessário e alteração aprovada antes
de continuar no DevOps.

## 10. Ferramentas

- **PyTest:** execução dos testes do backend Python;
- **Vitest:** execução dos testes do frontend React/TypeScript;
- **unittest.mock, mocks e fakes:** isolamento de dependências nos testes
  unitários;
- **monkeypatch:** simulação de variáveis de ambiente e configurações;
- **PostgreSQL:** dependência real usada nos testes de integração;
- **fixtures:** dados controlados usados para preparar o banco de teste;
- **Coverage Gutters:** visualização da cobertura durante o desenvolvimento;
- **CI:** execução automatizada dos comandos já definidos pelo processo.

## 11. Fala para a apresentação

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
