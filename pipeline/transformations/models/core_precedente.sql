MODEL (
  name core.precedente,
  kind FULL,
  grain (corte, tipo, numero),
  audits (
    not_null(columns := (corte, tipo, numero, enunciado, origem)),
    unique_combination_of_columns(columns := (corte, tipo, numero)),
    precedente_de_corte_conhecida,
    precedente_com_enunciado,
    precedente_com_volume
  )
);

/*
  O que as Cortes Superiores firmaram, e que as decisões citam.

  Não existe catálogo público de súmulas: o portal de dados abertos do STJ não
  publica nenhum, o BDJur só tem manuais da Secretaria de Jurisprudência, e o
  scon responde 403 a quem se identifica. O enunciado é reconstruído do próprio
  acervo, onde as decisões o transcrevem entre aspas.

  A repetição é a verificação. 1.994 decisões escreveram a mesma frase para a
  Súmula 7 do STJ; o piso de três transcrições idênticas descarta o recorte que
  pegou texto vizinho por acidente.

  Sem corte declarada não há precedente: Súmula 7 do STJ e Súmula 7 do STF são
  coisas diferentes, e uma citação que não diz qual não tem chave. São 371
  súmulas, cobrindo 97,2% das citações de súmula.

  `situacao` fica nula de propósito. Súmula cancelada continua sendo citada em
  decisão antiga, e apresentar cancelada como vigente é erro grave numa
  ferramenta jurídica — a tela diz que não sabe, nunca assume.
*/
WITH citado AS (
  SELECT (REGEXP_MATCHES(
    UNACCENT(LOWER(REGEXP_REPLACE(ementa, '\s+', ' ', 'g'))),
    'sumula\s*(?:n[.oº°]*\s*)?([0-9]{1,4})\s*[/, -]*(?:do\s+)?(stj|stf)[^"]{0,70}"([^"]{40,})"',
    'g'
  )) AS achado
  FROM core.decisao
  WHERE ementa ~* 'S[uú]mula'
),

transcricao AS (
  SELECT
    UPPER(achado[2])  AS corte,
    achado[1]::BIGINT AS numero,
    BTRIM(achado[3])  AS enunciado,
    COUNT(*)          AS vezes
  FROM citado
  WHERE LENGTH(BTRIM(achado[3])) BETWEEN 40 AND 400
  GROUP BY 1, 2, 3
),

sumula AS (
  SELECT DISTINCT ON (corte, numero)
    corte              AS corte,
    'sumula'           AS tipo,
    numero             AS numero,
    enunciado          AS enunciado,
    CAST(NULL AS TEXT) AS situacao,
    CAST(NULL AS DATE) AS data,
    'reconstruido'     AS origem,
    vezes              AS transcricoes
  FROM transcricao
  WHERE vezes >= 3
  ORDER BY corte, numero, vezes DESC
),

/* O catálogo repete a mesma linha quando o tema tem vários processos ligados:
   mesmo sequencial, mesma tese. Tema sem tese firmada ainda está em
   julgamento e não é precedente — é pergunta. */
tema AS (
  SELECT DISTINCT ON (numero)
    'STJ'                                       AS corte,
    'tema'                                      AS tipo,
    "numeroPrecedente"::BIGINT                  AS numero,
    BTRIM("teseFirmada")                        AS enunciado,
    NULLIF(BTRIM(situacao), '')                 AS situacao,
    TO_DATE(NULLIF("dataJulgamento", ''), 'YYYY-MM-DD') AS data,
    'catalogo'                                  AS origem,
    CAST(NULL AS BIGINT)                        AS transcricoes
  FROM raw.precedente_stj
  WHERE "tipoPrecedente" = 'Tema'
    AND COALESCE(BTRIM("teseFirmada"), '') <> ''
    AND "numeroPrecedente" ~ '^[0-9]+$'
  ORDER BY numero, "dataJulgamento" DESC NULLS LAST
)

SELECT corte, tipo, numero, enunciado, situacao, data,
       CAST(NULL AS TEXT) AS url_fonte, origem, transcricoes, NOW() AS carregado_em
FROM sumula
UNION ALL
SELECT corte, tipo, numero, enunciado, situacao, data,
       CAST(NULL AS TEXT) AS url_fonte, origem, transcricoes, NOW() AS carregado_em
FROM tema

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (tipo, numero);
JINJA_END;
