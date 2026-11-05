MODEL (
  name core.busca_ampla,
  kind FULL,
  grain (lexema, fonte_codigo, identificador_fonte),
  audits (
    not_null(columns := (lexema, posicao, rank, data_referencia, fonte_codigo, identificador_fonte)),
    unique_combination_of_columns(columns := (lexema, fonte_codigo, identificador_fonte)),
    busca_ampla_cobre_todo_termo_frequente,
    busca_ampla_na_mesma_ordem
  )
);

/*
  As primeiras páginas já ranqueadas, para as palavras que não cabem no teto de
  tempo da busca.

  O problema é `core.termo_frequente`: pontuar 765.840 ementas para devolver as
  vinte primeiras custa 95,3 s na produção. A observação que resolve é que o
  `ts_rank` de uma consulta de um lexema só depende daquele lexema naquele
  documento — não depende de mais nada da consulta. Logo ele pode ser calculado
  uma vez, guardado, e lido depois.

  E guardado quer dizer o valor mesmo, não uma aproximação. A ordem desta
  tabela é a ordem que a busca produz hoje, posição por posição: conferido
  contra o caminho atual nas 100 primeiras de `recurso`, 0 divergências. É o
  que o critério da história exige — ganhar velocidade sem mudar o que o
  usuário vê.

  O ganho medido sobre o acervo, pedindo a primeira página de `recurso` pelas
  instruções que o backend executa de verdade:

    caminho de hoje    contagem 484 ms + página 757 ms = 1.241 ms no PC
                       95,3 s na produção
    esta tabela        termo 1,03 ms + página 35,68 ms = 36,71 ms no PC
                       34 vezes mais rápido, mesma página posição por posição

  Dos 36,71 ms, a leitura do índice é 0,043 ms — o resto é o `ts_headline` que
  recorta o trecho de 20 ementas. É esse o ponto: o que sobrou de caro custa por
  linha devolvida, e são sempre vinte, não por casamento, que podem ser
  setecentos mil.

  Mil linhas por lexema, não o acervo inteiro. São 50 páginas de 20, e
  materializar as 84 milhões de postagens acima do piso dobraria o banco para
  servir páginas que ninguém abre. Quem passar da página 50 numa busca de uma
  palavra só cai no caminho antigo e espera — é raro e é correto, que é melhor
  do que ser rápido e errado.

  Construção medida sobre o acervo inteiro em 02/11/2026: 1.172 termos,
  1.172.000 linhas, 5 min 54 s, 211 MB com os dois índices. O custo cai sobre o
  PC onde o pipeline roda, não sobre os servidores.

  A tabela precisa ser reconstruída junto com `core.decisao`, não depois: uma
  decisão nova com rank alto que não esteja aqui sairia da primeira página de
  `recurso` até a próxima reconstrução, e aí a ordem deixaria de ser a mesma.
*/

SELECT
  t.lexema,
  r.posicao::INTEGER            AS posicao,
  r.rank::REAL                  AS rank,
  r.data_referencia,
  r.fonte_codigo,
  r.identificador_fonte
FROM core.termo_frequente AS t
CROSS JOIN LATERAL (
  SELECT
    ROW_NUMBER() OVER (
      ORDER BY
        TS_RANK(d.ementa_busca, QUOTE_LITERAL(t.lexema)::TSQUERY) DESC,
        d.data_referencia DESC,
        d.fonte_codigo DESC,
        d.identificador_fonte DESC
    ) AS posicao,
    TS_RANK(d.ementa_busca, QUOTE_LITERAL(t.lexema)::TSQUERY) AS rank,
    d.data_referencia,
    d.fonte_codigo,
    d.identificador_fonte
  FROM core.decisao AS d
  /* O literal convertido em tsquery, e não `to_tsquery`. O lexema já saiu do
     analisador e do radicalizador quando entrou no tsvector; devolvê-lo para
     lá o processa de novo, e o resultado não é o mesmo lexema em dois casos,
     os dois medidos sobre os 1.183 termos acima do piso:

       214 mudam de radical    `acorda` (323.845 decisões) vira `acord`
        11 têm hífen           `fatico-probatori` (89.404) vira a frase
                               'fatico-probatori' <-> 'fatico' <-> 'probatori'

     Os dois erram do mesmo jeito: o termo deixa de casar e a tabela fica sem
     nenhuma linha para ele. Foi assim que o defeito apareceu — a primeira
     construção usou `to_tsquery` e veio mil linhas mais curta para cada termo
     com hífen, em silêncio. O conversor de entrada do tsquery não analisa
     nada: lê o lexema como ele é. */
  WHERE d.ementa_busca @@ QUOTE_LITERAL(t.lexema)::TSQUERY
  ORDER BY
    TS_RANK(d.ementa_busca, QUOTE_LITERAL(t.lexema)::TSQUERY) DESC,
    d.data_referencia DESC,
    d.fonte_codigo DESC,
    d.identificador_fonte DESC
  LIMIT 1000
) AS r

;

JINJA_STATEMENT_BEGIN;
/*
  Sem nome fixo, pela mesma razão que em `core_decisao.sql`: o SQLMesh cria uma
  tabela física nova a cada mudança do modelo e o nome do índice é único por
  schema.

  O primeiro índice é o que faz a história funcionar. Ele carrega todas as
  colunas que a página precisa, na ordem exata em que a página as pede, então o
  Postgres responde com Index Only Scan e zero visitas ao heap.
*/
CREATE INDEX ON {{ this_model }} (lexema, rank DESC, data_referencia DESC, fonte_codigo DESC, identificador_fonte DESC);
CREATE UNIQUE INDEX ON {{ this_model }} (lexema, fonte_codigo, identificador_fonte);
JINJA_END;
