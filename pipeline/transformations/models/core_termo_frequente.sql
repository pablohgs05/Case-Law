MODEL (
  name core.termo_frequente,
  kind FULL,
  grain (lexema),
  audits (
    not_null(columns := (lexema, decisoes)),
    unique_combination_of_columns(columns := (lexema)),
    termo_frequente_acima_do_teto
  )
);

/*
  As palavras que o acervo usa tantas vezes que buscar por uma delas não cabe
  no orçamento de tempo da busca.

  O número que define "tantas vezes" foi medido, não arbitrado. Na produção em
  31/10/2026, com 991.163 decisões:

    recurso      765.840 decisões    1.205 MB de tsvector    95,3 s
    direito      309.257               487 MB               39,3 s
    prazo        121.402               191 MB               29,5 s
    dano moral    29.783                47 MB                0,6 s

  Dividindo os três primeiros, o disco da VPS entrega 12,4 a 12,6 MB/s para
  esse acesso. O índice GIN acha os casamentos em 40 ms; o custo é ler
  `ementa_busca` de volta do TOAST para o `ts_rank` pontuar cada casamento, e
  `ementa_busca` é a maior coluna da tabela — 1.488 MB, mais que a própria
  ementa.

  A conta fecha o corte: um teto de 2 s a 12,5 MB/s são 25 MB, e a 1.574 bytes
  de tsvector por decisão são 16 mil decisões. Daí o piso de 16.000. Acima
  dele a busca não cabe no teto e precisa do ranqueamento materializado em
  `core.busca_ampla`; abaixo, o caminho de hoje já responde.

  Medido sobre o acervo, 1.183 lexemas passam do piso e 1.172 ficam, pela
  razão explicada no HAVING. `dano moral` não passa porque é a interseção de
  dois lexemas, e interseção de palavra comum com palavra comum é um conjunto
  pequeno: é por isso que a lentidão é quase sempre de busca por uma palavra
  só.

  A contagem também serve como total exato da busca. Quem pesquisa `recurso`
  recebe 765.840 sem que ninguém conte nada na hora: está aqui.
*/

SELECT
  l.lexema::TEXT                AS lexema,
  COUNT(*)::BIGINT              AS decisoes,
  MAX(d.carregado_em)           AS carregado_em
FROM core.decisao AS d
/* `tsvector_to_array` devolve cada lexema uma vez por documento, então
   COUNT(*) é a quantidade de decisões e não a de ocorrências. */
CROSS JOIN LATERAL UNNEST(TSVECTOR_TO_ARRAY(d.ementa_busca)) AS l(lexema)
GROUP BY l.lexema
HAVING COUNT(*) >= 16000
   /* Só lexema que uma palavra digitada consegue produzir sozinha. O analisador
      do Postgres parte palavra composta em pedaços: `fatico-probatori` vira a
      frase 'fatico-probatori' <-> 'fatic' <-> 'probatori', cinco nós, e quem
      digita "fático-probatório" nunca chega a um lexema só.

      São 11 dos 1.183 que passam do piso, e guardar o ranking deles seria pior
      do que inútil. Conferido sobre o acervo: a ordem armazenada de
      `fatico-probatori` diverge da ordem da busca em 96 das 100 primeiras
      posições, porque uma é o ranking de um lexema e a outra o de uma frase de
      três. Hoje o portão do backend não as deixa passar; guardadas aqui, elas
      viram uma armadilha para quem afrouxar o portão amanhã.

      Essas buscas continuam lentas: `fatico-probatori` casa 89.404 decisões,
      cerca de 11 s na produção pela conta de 12,5 MB/s. Estão fora do alcance
      desta história, não resolvidas por ela. */
   AND NUMNODE(TO_TSQUERY('simple', QUOTE_LITERAL(l.lexema))) = 1
