# Integração — entrega posterior, não apresentar na aula unitária

Status em 22/10/2026: TEST_DATABASE_URL ausente; Docker e psql não encontrados no PATH; caminhos padrão Docker/PostgreSQL ausentes. Não há ambiente de banco executável neste computador. Os 195 ignorados históricos não são aprovação. Não instalamos/alteramos serviços de produção.

## Preparação isolada entregue

`docker-compose.test.yml` usa projeto próprio `case-law-tests`, serviço `postgres-test`, porta local 55432 e banco `caselaw_test` com usuário próprio. Dados ficam em memória e somem ao remover o contêiner. Credencial é pública e descartável exclusivamente local, sem ligação com ambientes existentes. Não usa o compose de desenvolvimento nem volumes de produção. Requer Docker funcionando; se a porta estiver ocupada, resolver o conflito antes de iniciar.

Na raiz, numa máquina com Docker e dependências backend preparadas:

```powershell
docker compose -f docker-compose.test.yml up -d --wait
# Somente esta URL local descartável; fixtures apagam/recriam schema core.
$env:TEST_DATABASE_URL = 'postgresql://caselaw_test:local_test_only@127.0.0.1:55432/caselaw_test'
cd backend
uv run pytest tests/test_scrum_ementa_integration.py -m integration -v -rs
uv run pytest -m integration -v -rs
cd ..
docker compose -f docker-compose.test.yml down
Remove-Item Env:TEST_DATABASE_URL
```

O schema de fixtures cria pg_trgm, unaccent e vector. Primeiro teste: API + consulta + banco reais, decisão 1000004 com todas as seções. Nenhuma credencial de produção é necessária. Não apontar TEST_DATABASE_URL para banco útil: `prepared_database` recria schema core.

## Próxima tarefa e aceite

1. Confirmar com professor/equipe recorte de integração, critérios, história/sprint e responsáveis em planning própria.
2. Integrante com Docker executa ambiente e teste focal, depois suíte. Registrar SHA, versões, comandos, resultados e logs novos.
3. Exigir cenários obrigatórios executados, zero falhas/erros e nenhum obrigatório ignorado; saída 0 com skips é insuficiente.
4. Outro integrante revisa evidências; autor corrige se necessário; executar/revisar novamente.

Configuração preparada e revisada como texto, **não validada por Docker neste ambiente**. Contagem esperada historicamente: 195 cenários; confirmar a contagem da execução futura. CI, ReqTrack, deploy e banco de desenvolvimento permanecem fora deste trabalho. A PR #1 preserva o teste de integração em arquivo separado; aceite unitário não conclui essa entrega posterior.
