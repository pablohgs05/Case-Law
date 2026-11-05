MODEL (
  name core.doutrina_termo,
  kind FULL,
  grain (repositorio, identificador_oai, termo),
  audits (
    not_null(columns := (repositorio, identificador_oai, termo, peso)),
    unique_combination_of_columns(columns := (repositorio, identificador_oai, termo)),
    termo_de_obra_existente,
    termo_acima_do_piso,
    termo_com_cobertura
  )
);

/*
  O vocabulário da doutrina, com o quanto cada palavra distingue uma obra das
  outras. É a tabela que faz a sugestão falar de assunto em vez de processo.

  O problema que ela resolve foi medido. A tese de uma decisão é prosa
  processual: "não configura cerceamento de defesa o julgamento antecipado da
  lide". Casando por busca textual, as obras que vencem são as que
  compartilham essas palavras — e todas compartilham, porque toda decisão as
  escreve. A primeira colocada para uma tese sobre poluição por derramamento
  de óleo era um artigo sobre prescrição de ação acidentária.

  O peso é a raridade do termo na linguagem judicial, não no acervo de
  doutrina. Medido sobre as 991.163 ementas:

    prov       19,7% das decisões   peso 0,82
    sumula     8.008 decisões       peso 1,07
    dano       5.604                peso 2,46
    lide         598                peso 3,34
    ambiental     93                peso 5,09
    poluicao       8                peso 11,7

  Palavra de processo é comum e pesa pouco; palavra de assunto é rara e pesa
  muito. Com esse peso, a mesma tese passou a trazer jurisdição ambiental,
  responsabilidade por dano ambiental e catástrofes ambientais nas primeiras
  posições.

  Dois cortes. Peso mínimo 2,0 descarta o termo presente em mais de 13% das
  decisões, que não distingue nada. Radical com menos de quatro letras sai
  porque é quase sempre acidente do radicalizador: `via` casa "via adequada"
  com "terceira via", `ger` casa qualquer coisa com "gera".

  Só o vocabulário da doutrina entra. Termo que nenhuma obra usa não casa com
  nada, e varrer as 548.197 palavras distintas das ementas para guardar peso
  de palavra inútil custa tempo de carga e não muda resultado.
*/

WITH vocabulario AS (
  SELECT DISTINCT
    d.repositorio       AS repositorio,
    d.identificador_oai AS identificador_oai,
    t.lexeme            AS termo
  FROM core.doutrina AS d, UNNEST(d.busca) AS t
  WHERE LENGTH(t.lexeme) >= 4
),

acervo AS (
  SELECT COUNT(*)::DOUBLE PRECISION AS decisoes FROM core.decisao
),

judicial AS (
  SELECT
    t.lexeme  AS termo,
    COUNT(*)  AS decisoes
  FROM core.decisao AS d, UNNEST(TO_TSVECTOR('portugues_sem_acento', d.ementa)) AS t
  WHERE EXISTS (SELECT 1 FROM vocabulario AS v WHERE v.termo = t.lexeme)
  GROUP BY 1
)

SELECT
  v.repositorio                                             AS repositorio,
  v.identificador_oai                                       AS identificador_oai,
  v.termo                                                   AS termo,
  COALESCE(j.decisoes, 0)                                   AS decisoes,
  LN(a.decisoes / GREATEST(COALESCE(j.decisoes, 0), 1))     AS peso,
  NOW()                                                     AS carregado_em
FROM vocabulario AS v
CROSS JOIN acervo AS a
LEFT JOIN judicial AS j
  ON j.termo = v.termo
WHERE LN(a.decisoes / GREATEST(COALESCE(j.decisoes, 0), 1)) >= 2.0

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (repositorio, identificador_oai, termo);
CREATE INDEX ON {{ this_model }} (termo);
JINJA_END;
