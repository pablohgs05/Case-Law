MODEL (
  name core.doutrina,
  kind FULL,
  grain (repositorio, identificador_oai),
  audits (
    not_null(columns := (repositorio, identificador_oai, titulo, url_fonte)),
    unique_combination_of_columns(columns := (repositorio, identificador_oai)),
    doutrina_de_acesso_aberto,
    doutrina_com_titulo,
    doutrina_com_link_do_acervo,
    doutrina_sem_texto_integral,
    doutrina_com_ano_plausivel,
    doutrina_com_cobertura_de_assunto
  )
);

/*
  A doutrina que pode ser apontada ao lado de uma decisão: autor, título,
  onde saiu e o link para o acervo. Nunca o texto da obra.

  A coleção é a garantia, não o campo. `dc:rights` só aparece em 5,8% dos
  registros, então exigi-lo deixaria de fora 94% do acervo aberto; o que
  sustenta o escopo é o próprio STJ ter separado Acesso Aberto (col_2011_8) de
  Acesso Restrito (col_2011_9) em coleções distintas. A classificação é da
  biblioteca, não nossa.

  Onde o campo aparece, ele manda. Um registro arquivado em Acesso Aberto
  declara "Restricted access" no próprio `dc:rights` — 1 em 798 na amostra. A
  regra é lista de permissão: direitos desconhecido exclui a obra em vez de
  incluí-la.

  `data` fica como a biblioteca escreveu, texto. Data de publicação é parcial
  por natureza — 1976, 2001-12, 1997/1998 — e transformar isso em DATE inventa
  dia e mês que ninguém registrou. `ano` existe ao lado para ordenar e filtrar.

  São três datas e cada uma responde por uma coisa. `data` é quando a obra foi
  publicada. `arquivada_em` é o primeiro `dc:date`, que em todos os 798
  registros é a entrada no acervo: uma obra de 1976 digitalizada em 2019 traz
  as duas, e apresentar a segunda como data da obra erra por quatro décadas.
  `alterada_em` é o relógio do protocolo — quando o registro mudou — e é o
  cursor que o `from` do OAI-PMH compara na coleta incremental.

  `busca` é por onde a doutrina casa com a decisão, e carrega título e assunto,
  não resumo. O resumo existe em 31,8% dos registros e quando existe costuma
  ser sumário ou nota de evento — "Palestra proferida na 6ª Reunião do Fórum
  Permanente de História do Direito" não diz o que o texto sustenta, e indexar
  isso traz obra errada com cara de certa. Título está em 100% e é descritivo
  em Direito; assunto está em 54,8% e é palavra-chave escolhida por quem
  catalogou. Os dois com peso A; o título traduzido com peso B, porque repete
  o primeiro em outra língua.

  O link é normalizado para um resolvedor só. Um registro em 798 aponta para
  hdl.handle.net, o resolvedor canônico do Handle System, em vez do endereço do
  BDJur; é o mesmo handle e abre o mesmo registro. Uniformizar aqui deixa a
  tela com um único padrão de link e mantém exata a auditoria que confere o
  handle contra o identificador OAI.
*/

WITH aberto AS (
  SELECT b.*
  FROM raw.doutrina_bdjur AS b
  WHERE EXISTS (
    SELECT 1
    FROM JSONB_ARRAY_ELEMENTS_TEXT(b.conjuntos) AS c (codigo)
    WHERE c.codigo = 'col_2011_8'
  )
    AND (b.direitos IS NULL OR b.direitos ~* 'acesso aberto|open access')
)

SELECT
  a.repositorio                                       AS repositorio,
  a.identificador_oai                                 AS identificador_oai,
  a.titulo                                            AS titulo,
  COALESCE((SELECT ARRAY_AGG(v ORDER BY i)
     FROM JSONB_ARRAY_ELEMENTS_TEXT(a.titulos) WITH ORDINALITY AS t (v, i)
    WHERE i > 1), ARRAY[]::TEXT[])                    AS titulos_alternativos,
  COALESCE((SELECT ARRAY_AGG(v ORDER BY i)
     FROM JSONB_ARRAY_ELEMENTS_TEXT(a.autores) WITH ORDINALITY AS t (v, i)),
    ARRAY[]::TEXT[])                                  AS autores,
  COALESCE((SELECT ARRAY_AGG(v ORDER BY i)
     FROM JSONB_ARRAY_ELEMENTS_TEXT(a.assuntos) WITH ORDINALITY AS t (v, i)),
    ARRAY[]::TEXT[])                                  AS assuntos,
  a.tipo                                              AS tipo,
  a.data                                              AS data,
  a.ano                                               AS ano,
  LOWER(REPLACE(a.idioma, '_', '-'))                  AS idioma,
  a.publicacao                                        AS publicacao,
  a.resumo                                            AS resumo,
  a.referencia                                        AS referencia,
  REGEXP_REPLACE(a.url_fonte, '^https?://hdl\.handle\.net/',
                 'https://bdjur.stj.jus.br/handle/')  AS url_fonte,
  a.direitos                                          AS direitos,
  COALESCE((SELECT ARRAY_AGG(v ORDER BY i)
     FROM JSONB_ARRAY_ELEMENTS_TEXT(a.conjuntos) WITH ORDINALITY AS t (v, i)),
    ARRAY[]::TEXT[])                                  AS conjuntos,
  a.arquivada_em                                      AS arquivada_em,
  a.alterada_em                                       AS alterada_em,
  SETWEIGHT(TO_TSVECTOR('portugues_sem_acento', a.titulo), 'A') ||
  SETWEIGHT(TO_TSVECTOR('portugues_sem_acento',
    COALESCE((SELECT STRING_AGG(v, ' ')
       FROM JSONB_ARRAY_ELEMENTS_TEXT(a.assuntos) AS t (v)), '')), 'A') ||
  SETWEIGHT(TO_TSVECTOR('portugues_sem_acento',
    COALESCE((SELECT STRING_AGG(v, ' ')
       FROM JSONB_ARRAY_ELEMENTS_TEXT(a.titulos) WITH ORDINALITY AS t (v, i)
      WHERE i > 1), '')), 'B')                        AS busca,
  NOW()                                               AS carregado_em
FROM aberto AS a

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (repositorio, identificador_oai);
CREATE INDEX ON {{ this_model }} USING gin (busca);
CREATE INDEX ON {{ this_model }} (ano);
JINJA_END;
