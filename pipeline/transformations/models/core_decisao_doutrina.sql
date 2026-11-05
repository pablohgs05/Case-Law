MODEL (
  name core.decisao_doutrina,
  kind FULL,
  grain (fonte_codigo, identificador_fonte, repositorio, identificador_oai),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, repositorio, identificador_oai, nota)),
    unique_combination_of_columns(
      columns := (fonte_codigo, identificador_fonte, repositorio, identificador_oai)
    ),
    sugestao_de_decisao_com_tese,
    sugestao_de_obra_existente,
    sugestao_acima_do_limite,
    sugestao_com_termo_proprio,
    sugestao_com_cobertura
  )
);

/*
  A doutrina que vale apontar ao lado de uma decisão. Casa a tese firmada —
  a proposição jurídica da SCRUM-111, não dissertação de doutorado — com o
  título e o assunto das obras do acervo aberto.

  Sugestão ruim é pior que nenhuma sugestão. Um artigo sobre outro assunto
  apresentado como relacionado faz o leitor perder tempo e perder confiança na
  ferramenta inteira, então o limite é escolhido para calar e não para chutar.
  São três condições, e a tabela só guarda o que passa pelas três:

    nota      >= 9,0   soma dos pesos dos termos que a tese e a obra dividem
    termos    >= 2     uma palavra em comum é coincidência
    forte     >= 4,5   ao menos um termo raro na linguagem judicial
    distancia <= 8     os termos casados formam expressão, não acaso

  A terceira é a que mais corta, e corta o erro mais convincente. Uma tese
  sobre "adoção de medidas executivas atípicas" casava com "Possibilidade
  jurídica de adoção por casais homoafetivos" por três termos — `adoca`,
  `menor`, `pesso` —, nota 10,2 e nenhum deles próprio do assunto. Exigir um
  termo raro derruba essa, e mantém "Cláusulas abusivas nos contratos de
  financiamento" para a tese sobre alienação fiduciária, que casa em `fiduc`.

  O que o limite custa, medido sobre as 57.439 decisões com tese:

    nota >= 7,0 · forte >= 3,5                   55,8% recebem sugestão, 6,6 cada
    nota >= 9,0 · forte >= 4,5                   26,9% recebem sugestão, 2,8 cada
    nota >= 9,0 · forte >= 4,5 · distancia <= 8  20,8% recebem sugestão, 2,4 cada
    nota >= 12  · forte >= 5,0                   10,5% recebem sugestão, 1,8 cada

  A terceira linha é a escolhida: 28.423 ligações, 11.960 decisões, 557 das 797
  obras apontadas ao menos uma vez.

  Quatro em cada cinco decisões não recebem nada, e isso é o resultado certo,
  não falha: tese processual — habeas corpus, cumprimento de sentença, quebra
  de cadeia de custódia — não tem assunto de direito material para casar.

  O teto está no acervo, não no método. São 797 obras das 20.597 da coleção de
  acesso aberto, 3,9%, porque o endpoint do BDJur recusa acesso automatizado e
  a amostra foi salva à mão. A taxa de sugestão útil medida aqui é piso, e tem
  de ser remedida quando a coleta inteira entrar.

  A quarta condição é a que a nota não consegue dar: os termos casados têm de
  estar perto uns dos outros na tese. `distancia <= 8` palavras.

  A nota não distingue sugestão boa de ruim — isso foi medido, e é o resultado
  mais útil desta subtask. Nas 30 decisões avaliadas, as boas tiraram de 9,3 a
  33,4 e as ruins de 9,1 a 33,0: a pior sugestão de todas, um artigo sobre
  práticas comerciais desleais para uma tese sobre efeito suspensivo em
  apelação, tirou 33,0 — a segunda maior nota da amostra. Subir o limite
  cortaria boas e ruins na mesma proporção.

  O que distingue é se os termos formam um conceito ou estão espalhados.
  "litigância de má-fé", "união estável", "arguição de descumprimento de
  preceito fundamental" são expressões; `elaboraca` e `menor` casando a 20
  palavras de distância é coincidência. Medida nas mesmas 30: distância média
  2,6 nas úteis e 12,9 nas inúteis, e nenhuma útil acima de 8. O corte em 8
  mantém todas as úteis e derruba sete das inúteis.

  `casou_em` guarda os radicais, não as palavras. É o registro do que de fato
  casou, e é o que a tela precisa para dizer por que sugeriu — traduzir radical
  de volta para palavra é trabalho da apresentação, não daqui.
*/

WITH posicao AS (
  SELECT
    d.fonte_codigo         AS fonte_codigo,
    d.identificador_fonte  AS identificador_fonte,
    t.lexeme               AS termo,
    p.pos                  AS pos
  FROM core.decisao AS d,
    UNNEST(TO_TSVECTOR('portugues_sem_acento', d.tese)) AS t,
    UNNEST(t.positions) AS p (pos)
  WHERE d.tese IS NOT NULL
),

tese_termo AS (
  SELECT DISTINCT fonte_codigo, identificador_fonte, termo FROM posicao
),

candidato AS (
  SELECT
    tt.fonte_codigo              AS fonte_codigo,
    tt.identificador_fonte       AS identificador_fonte,
    dt.repositorio               AS repositorio,
    dt.identificador_oai         AS identificador_oai,
    SUM(dt.peso)                 AS nota,
    COUNT(*)                     AS termos,
    MAX(dt.peso)                 AS termo_mais_forte,
    ARRAY_AGG(dt.termo ORDER BY dt.peso DESC, dt.termo) AS casou_em
  FROM tese_termo AS tt
  JOIN core.doutrina_termo AS dt
    ON dt.termo = tt.termo
  GROUP BY 1, 2, 3, 4
  HAVING COUNT(*) >= 2
     AND SUM(dt.peso) >= 9.0
     AND MAX(dt.peso) >= 4.5
),

proximidade AS (
  SELECT
    c.fonte_codigo        AS fonte_codigo,
    c.identificador_fonte AS identificador_fonte,
    c.identificador_oai   AS identificador_oai,
    MIN(ABS(a.pos - b.pos)) AS distancia
  FROM candidato AS c
  JOIN posicao AS a
    ON a.fonte_codigo = c.fonte_codigo
   AND a.identificador_fonte = c.identificador_fonte
   AND a.termo = ANY (c.casou_em)
  JOIN posicao AS b
    ON b.fonte_codigo = c.fonte_codigo
   AND b.identificador_fonte = c.identificador_fonte
   AND b.termo = ANY (c.casou_em)
   AND b.termo <> a.termo
  GROUP BY 1, 2, 3
)

SELECT
  c.fonte_codigo        AS fonte_codigo,
  c.identificador_fonte AS identificador_fonte,
  c.repositorio         AS repositorio,
  c.identificador_oai   AS identificador_oai,
  c.nota                AS nota,
  c.termos              AS termos,
  c.termo_mais_forte    AS termo_mais_forte,
  c.casou_em            AS casou_em,
  p.distancia           AS distancia,
  NOW()                 AS carregado_em
FROM candidato AS c
JOIN proximidade AS p
  ON p.fonte_codigo = c.fonte_codigo
 AND p.identificador_fonte = c.identificador_fonte
 AND p.identificador_oai = c.identificador_oai
WHERE p.distancia <= 8

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (
  fonte_codigo, identificador_fonte, repositorio, identificador_oai
);
CREATE INDEX ON {{ this_model }} (fonte_codigo, identificador_fonte, nota DESC);
CREATE INDEX ON {{ this_model }} (repositorio, identificador_oai);
JINJA_END;
