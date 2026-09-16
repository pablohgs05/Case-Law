# Processo de testes unitários

Este documento descreve exclusivamente a entrega de testes unitários do
Case-Law e sua relação com o processo de DevOps. O escopo acompanha o estado
atual do projeto: a aplicação possui uma configuração baseada em ambiente.
Não foram criadas regras de negócio fictícias apenas para aumentar a
quantidade de testes.

## Objetivo e escopo

O alvo escolhido é `backend/app/config.py`. Esse módulo transforma a variável
`CORS_ORIGINS` em uma lista e define valores padrão. Uma alteração incorreta
pode impedir a comunicação do frontend com a API.

O foco é testar lógica de aplicação, e não infraestrutura externa como
PostgreSQL, servidor HTTP ou navegador. Quando novas regras de negócio forem
implementadas, elas poderão receber testes unitários próprios.

## Estratégia

Cada cenário segue a estrutura **Given / When / Then**:

1. **Given (Dado):** prepara os valores de ambiente.
2. **When (Quando):** cria uma instância de `Settings`.
3. **Then (Então):** verifica o resultado esperado.

Os testes de `backend/tests/test_config.py` isolam o comportamento de
configuração e usam `monkeypatch` para simular variáveis de ambiente sem
alterar a máquina ou um arquivo `.env` real. Como o módulo não possui
dependências externas, não é necessário usar mocks neste momento.

## Cenários unitários

- usa o frontend local quando `CORS_ORIGINS` não foi definido;
- aceita uma única origem;
- separa múltiplas origens por vírgula e remove espaços;
- lê `ENVIRONMENT` do ambiente.

## Como executar

Na raiz do repositório:

```bash
cd backend
uv sync --locked
uv run pytest -m unit -v
```

O resultado esperado é:

```text
4 passed
```

Também é possível executar a suíte completa existente com `uv run pytest`, mas
a demonstração desta entrega deve usar o marcador `unit`.

## Resultado e fluxo de DevOps

O resultado esperado desta entrega é **4 testes unitários aprovados**. Uma
falha significa que o comportamento da configuração pode ter sido alterado:
o desenvolvedor investiga o cenário, corrige o código ou o teste e executa
novamente antes de considerar a alteração pronta.

O fluxo fica:

```text
Código de configuração alterado
        ↓
Testes unitários locais
        ↓
Resultado dos testes
        ↓
Registro/documentação do resultado
        ↓
Código preparado para ser incluído futuramente no fluxo DevOps
```

Essa entrega não implementa CI. Ela fornece testes determinísticos, dependências
declaradas, um comando reproduzível e um resultado de sucesso ou falha que
poderá ser consumido pelo pipeline posteriormente.

Cobertura é um indicador de alcance, não uma prova de qualidade perfeita. Um
teste pode executar uma linha e ainda verificar uma expectativa fraca. Por isso,
os cenários foram escolhidos com base no risco e no comportamento observável,
e não apenas no percentual de linhas.

## Perguntas para a apresentação

- **Por que `test_config.py` é unitário?** A unidade é o comportamento de
  conversão da configuração; o ambiente é simulado e nenhum HTTP, banco ou
  servidor é usado.
- **Por que usar `monkeypatch`?** Ele simula as variáveis de ambiente durante o
  teste e restaura o estado depois, mantendo o teste isolado e repetível.
- **Por que não usar mock?** O módulo testado não possui dependências externas.
  Adicionar um mock sem necessidade não aumentaria a validade do teste.
- **O que acontece se falhar?** `pytest` retorna código diferente de zero; a
  falha deve ser registrada e corrigida antes de considerar a alteração pronta.
- **Como isso se relaciona com DevOps?** O teste automatiza uma verificação
  repetível de qualidade e produz um resultado que poderá ser consumido pelo
  pipeline no futuro, sem implementar CI nesta etapa.
