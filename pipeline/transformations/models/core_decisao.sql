MODEL (
  name core.decisao,
  kind FULL,
  grain (fonte_codigo, identificador_fonte),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, tribunal_sigla, ementa, data_referencia, url_fonte)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte)),
    sem_segredo_de_justica,
    data_referencia_preenchida
  )
);

/*
  Um acórdão, pronto para consulta.

  Registros em segredo de justiça não entram: o TJDFT devolve o campo mas NÃO
  oculta o conteúdo, então o descarte é responsabilidade de quem coleta.

  data_referencia existe porque nem toda fonte devolve as duas datas. É ela que
  filtro (US3), ordenação (US6) e desempate da paginação (US7) usam.
*/

WITH bruto AS (
  SELECT
    identificador,
    "dataJulgamento"::DATE               AS data_julgamento,
    "dataPublicacao"::DATE               AS data_publicacao,
    processo,
    "descricaoOrgaoJulgador"             AS orgao_julgador,
    NULLIF(TRIM("nomeRelator"), '')      AS relator,
    "codigoClasseCnj"                    AS classe_cnj,
    ementa,
    NULLIF(TRIM(decisao), '')            AS decisao_texto,
    COALESCE("turmaRecursal", FALSE)     AS turma_recursal,
    COALESCE("possuiInteiroTeor", FALSE) AS possui_inteiro_teor,
    _dlt_load_id                         AS carga_id,
    'tjdft-jurisdf'                      AS fonte_codigo
  FROM raw.acordao_tjdft
  WHERE NOT COALESCE("segredoJustica", FALSE)
)

SELECT
  b.fonte_codigo                                        AS fonte_codigo,
  b.identificador                                       AS identificador_fonte,
  f.tribunal_sigla                                      AS tribunal_sigla,
  b.processo                                            AS processo,
  b.orgao_julgador                                      AS orgao_julgador,
  b.relator                                             AS relator,
  b.classe_cnj                                          AS classe_cnj,
  b.data_julgamento                                     AS data_julgamento,
  b.data_publicacao                                     AS data_publicacao,
  COALESCE(b.data_julgamento, b.data_publicacao)        AS data_referencia,
  b.ementa                                              AS ementa,
  'ementa_completa'                                     AS tipo_texto,
  b.decisao_texto                                       AS decisao_texto,
  CAST(NULL AS TEXT)                                    AS conhecimento,
  CAST(NULL AS TEXT)                                    AS resultado,
  CAST(NULL AS TEXT)                                    AS deliberacao,
  b.turma_recursal                                      AS turma_recursal,
  b.possui_inteiro_teor                                 AS possui_inteiro_teor,
  REPLACE(f.url_documento_template, '{identificador}', b.identificador) AS url_fonte,
  v.valido                                              AS link_valido,
  b.carga_id                                            AS carga_id,
  NOW()                                                 AS carregado_em,
  TO_TSVECTOR('portugues_sem_acento', b.ementa)         AS ementa_busca
FROM bruto AS b
JOIN core.fonte AS f ON f.codigo = b.fonte_codigo
LEFT JOIN verificacao.link AS v ON v.identificador = b.identificador

;

JINJA_STATEMENT_BEGIN;
/*
  Sem nome fixo de propósito. O SQLMesh cria uma tabela física nova a cada
  mudança do modelo, e no Postgres o nome do índice é único por SCHEMA, não por
  tabela: com nome fixo, o IF NOT EXISTS encontrava o índice preso à tabela
  anterior e pulava a criação, deixando a tabela em uso sem índice nenhum.
  Sem nome, o Postgres gera um por tabela e a colisão deixa de existir.
*/
CREATE UNIQUE INDEX ON {{ this_model }} (fonte_codigo, identificador_fonte);
CREATE INDEX ON {{ this_model }} USING gin (ementa_busca);
CREATE INDEX ON {{ this_model }} (data_referencia DESC, fonte_codigo, identificador_fonte);
CREATE INDEX ON {{ this_model }} (tribunal_sigla, data_referencia DESC);
CREATE INDEX ON {{ this_model }} (tribunal_sigla, orgao_julgador);
CREATE INDEX ON {{ this_model }} (tribunal_sigla, relator);
CREATE INDEX ON {{ this_model }} (processo);
CREATE INDEX ON {{ this_model }} (classe_cnj);
JINJA_END;
