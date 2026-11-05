MODEL (
  name core.decisao,
  kind FULL,
  grain (fonte_codigo, identificador_fonte),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, identificador_documento, tribunal_sigla, ementa, data_referencia, url_fonte)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte)),
    sem_segredo_de_justica,
    data_referencia_preenchida,
    data_do_stj_convertida,
    url_carrega_o_identificador,
    ementa_nao_vazia,
    token_do_documento_por_fonte,
    verdito_de_fonte_conhecida,
    tese_sem_secao_seguinte,
    tese_com_cobertura,
    url_aponta_para_um_acordao,
    deliberacao_de_valor_conhecido,
    deliberacao_com_cobertura,
    resultado_de_valor_conhecido,
    resultado_com_cobertura,
    resultado_sem_contradicao,
    classe_de_codigo_conhecido,
    classe_com_cobertura
  )
);

/*
  Um acórdão, pronto para consulta.

  Registros em segredo de justiça não entram: o TJDFT devolve o campo mas NÃO
  oculta o conteúdo, então o descarte é responsabilidade de quem coleta.

  data_referencia existe porque nem toda fonte devolve as duas datas. É ela que
  filtro (US3), ordenação (US6) e desempate da paginação (US7) usam.
*/

WITH RECURSIVE arvore_classe AS (
  SELECT codigo_cnj, codigo_cnj AS raiz
  FROM core.classe_processual
  WHERE codigo_pai IS NULL
  UNION ALL
  SELECT s.codigo_cnj, a.raiz
  FROM core.classe_processual AS s
  JOIN arvore_classe AS a ON s.codigo_pai = a.codigo_cnj
),

/* 88 nomes se repetem entre tribunais — "Ação Rescisória" existe em três
   códigos. Para o STJ vale o da árvore do próprio STJ (raiz 5); fora dela,
   o menor código, só para a escolha ser estável. */
classe AS (
  SELECT DISTINCT ON (chave) chave, codigo_cnj
  FROM (
    SELECT
      s.codigo_cnj,
      COALESCE(a.raiz, 0) AS raiz,
      UPPER(UNACCENT(TRIM(REGEXP_REPLACE(
      TRANSLATE(s.nome, E'\u00A0\u2007\u202F\u200B', '    '), '\s+', ' ', 'g')))) AS chave
    FROM core.classe_processual AS s
    LEFT JOIN arvore_classe AS a USING (codigo_cnj)
  ) AS x
  ORDER BY chave, (raiz = 5) DESC, codigo_cnj
),

-- The STJ writes the same organ both with and without accents. Whichever
-- spelling carries them is the one the screen should show.
orgao_stj AS (
  SELECT DISTINCT ON (UPPER(UNACCENT("nomeOrgaoJulgador")))
    UPPER(UNACCENT("nomeOrgaoJulgador")) AS chave,
    "nomeOrgaoJulgador"                  AS nome
  FROM raw.espelho_stj
  WHERE COALESCE(TRIM("nomeOrgaoJulgador"), '') <> ''
  ORDER BY
    UPPER(UNACCENT("nomeOrgaoJulgador")),
    ("nomeOrgaoJulgador" <> UNACCENT("nomeOrgaoJulgador")) DESC
),

bruto AS (
  SELECT
    identificador,
    uuid                                 AS identificador_documento,
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

  UNION ALL

  SELECT
    e.id                                                     AS identificador,
    e."numeroRegistro"                                       AS identificador_documento,
    TO_DATE(NULLIF(e."dataDecisao", ''), 'YYYYMMDD')         AS data_julgamento,
    -- Free text with the gazette and the page around it: DJE DATA:01/09/2010
    TO_DATE(
      (REGEXP_MATCH(e."dataPublicacao", '(\d{2}/\d{2}/\d{4})'))[1],
      'DD/MM/YYYY'
    )                                                        AS data_publicacao,
    NULLIF(TRIM(e."numeroProcesso"), '')                     AS processo,
    o.nome                                                   AS orgao_julgador,
    NULLIF(TRIM(e."ministroRelator"), '')                    AS relator,
    COALESCE(ci.codigo_cnj, ce.codigo_cnj)                   AS classe_cnj,
    e.ementa                                                 AS ementa,
    NULLIF(TRIM(e.decisao), '')                              AS decisao_texto,
    FALSE                                                    AS turma_recursal,
    FALSE                                                    AS possui_inteiro_teor,
    e._dlt_load_id                                           AS carga_id,
    'stj-espelhos'                                           AS fonte_codigo
  FROM raw.espelho_stj AS e
  LEFT JOIN orgao_stj AS o
    ON o.chave = UPPER(UNACCENT(e."nomeOrgaoJulgador"))
  /* O STJ nomeia a classe pela escada inteira: "AGRAVO REGIMENTAL NO RECURSO
     ESPECIAL". A tabela do CNJ só tem as peças soltas, e a classe é a mais
     externa — o agravo, não o recurso em que ele foi interposto. */
  LEFT JOIN classe AS ci
    ON ci.chave = UPPER(UNACCENT(TRIM(REGEXP_REPLACE(
      TRANSLATE(e."descricaoClasse", E'\u00A0\u2007\u202F\u200B', '    '), '\s+', ' ', 'g'))))
  LEFT JOIN classe AS ce
    ON ce.chave = REGEXP_REPLACE(UPPER(UNACCENT(TRIM(REGEXP_REPLACE(
      TRANSLATE(e."descricaoClasse", E'\u00A0\u2007\u202F\u200B', '    '), '\s+', ' ', 'g')))), '\s+(NOS|NAS|NO|NA|EM)\s+.*$', '')
  WHERE COALESCE(TRIM(e.ementa), '') <> ''
),

/*
  A tese que o próprio tribunal escreveu, quando escreveu.

  Desde 2024 o CNJ pede uma ementa em quatro seções, e a quarta é "DISPOSITIVO
  E TESE". Dentro dela o relator rotula o que firmou. 54.918 decisões trazem o
  rótulo — 34,5% do TJDFT e 2,0% do STJ, que tem acervo desde 1989.

  Os dois-pontos são obrigatórios: sem eles o padrão pega prosa, como em "tese
  de julgamento extra petita", e contamina 3.925 decisões do STJ.

  O bloco termina no primeiro "Dispositivos relevantes" ou "Jurisprudência
  relevante", que é a lista de citações que vem depois. Arrastá-la enche o card
  de referências e esconde a tese.

  A limpeza da borda esquerda tira aspas, sublinhados e travessões de
  diagramação; a da direita não tira o ponto final, que é do tribunal. Os dois
  conjuntos incluem \u00a0, o espaço não separável que os tribunais usam: sem
  ele a limpeza para no primeiro e deixa o lixo no texto.

  A separação em itens NÃO acontece aqui. Ela depende da consulta de quem
  pesquisa, então mora no backend.
*/
rotulada AS (
  SELECT
    fonte_codigo,
    identificador,
    SUBSTRING(
      ementa
      FROM REGEXP_INSTR(
        ementa,
        '(?i)teses?[[:space:]]+(de[[:space:]]+julgamento|firmadas?|fixadas?|adotada|do[[:space:]]+julgado)[[:space:]]*:',
        1, 1, 1
      )
    ) AS depois_do_rotulo
  FROM bruto
  WHERE ementa ~* 'teses?[[:space:]]+(de[[:space:]]+julgamento|firmadas?|fixadas?|adotada|do[[:space:]]+julgado)[[:space:]]*:'
),

tese AS (
  SELECT
    fonte_codigo,
    identificador,
    NULLIF(
      REGEXP_REPLACE(
        REGEXP_REPLACE(
          CASE
            WHEN REGEXP_INSTR(depois_do_rotulo, '(?i)(Dispositivos?[[:space:]]+relevantes?|Jurisprud[eê]ncia[[:space:]]+relevante)') > 0
            THEN SUBSTRING(depois_do_rotulo FOR REGEXP_INSTR(depois_do_rotulo, '(?i)(Dispositivos?[[:space:]]+relevantes?|Jurisprud[eê]ncia[[:space:]]+relevante)') - 1)
            ELSE depois_do_rotulo
          END,
          '^[[:space:]\u00a0"“”''_.–—-]+', ''
        ),
        '[[:space:]\u00a0"“”''_]+$', ''
      ),
      ''
    ) AS tese
  FROM rotulada
),

/* Três degraus acham o mérito quando o acórdão decidiu mais de uma coisa e
   cada uma teve sua votação: o que vem depois de "no mérito"; o primeiro
   marcador quando a maioria é sobre multa, honorários ou custas; senão o
   último. Dois recursos com votações diferentes não têm UMA deliberação. */
dispositivo AS (
  SELECT
    fonte_codigo,
    identificador,
    UNACCENT(LOWER(decisao_texto)) AS texto
  FROM bruto
  WHERE decisao_texto IS NOT NULL
),

deliberacao AS (
  SELECT
    fonte_codigo,
    identificador,
    texto,
    CASE
      WHEN texto LIKE '%no merito%' THEN SUBSTRING(texto FROM STRPOS(texto, 'no merito'))
      ELSE texto
    END AS escopo
  FROM dispositivo
),

votacao AS (
  SELECT
    fonte_codigo,
    identificador,
    texto,
    escopo,
    STRPOS(escopo, 'unanime')     AS unanime_primeiro,
    STRPOS(escopo, 'unanimidade') AS unanimidade_primeiro,
    STRPOS(escopo, 'maioria')     AS maioria_primeiro,
    CASE WHEN escopo LIKE '%unanime%'
         THEN LENGTH(escopo) - STRPOS(REVERSE(escopo), REVERSE('unanime')) + 1 ELSE 0 END AS unanime_ultimo,
    CASE WHEN escopo LIKE '%unanimidade%'
         THEN LENGTH(escopo) - STRPOS(REVERSE(escopo), REVERSE('unanimidade')) + 1 ELSE 0 END AS unanimidade_ultimo,
    CASE WHEN escopo LIKE '%maioria%'
         THEN LENGTH(escopo) - STRPOS(REVERSE(escopo), REVERSE('maioria')) + 1 ELSE 0 END AS maioria_ultimo
  FROM deliberacao
),

lida AS (
  SELECT
    fonte_codigo,
    identificador,
    CASE
      WHEN GREATEST(unanime_primeiro, unanimidade_primeiro) = 0 AND maioria_primeiro = 0 THEN NULL
      WHEN maioria_primeiro = 0 THEN 'unanime'
      WHEN GREATEST(unanime_primeiro, unanimidade_primeiro) = 0 THEN 'maioria'
      WHEN (
        SELECT COUNT(*) FROM REGEXP_MATCHES(
          escopo, 'recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] ', 'g'
        )
      ) >= 2 THEN NULL
      WHEN texto ~ 'multa|honorario|custas|prejudicad'
        THEN CASE
               WHEN LEAST(NULLIF(unanime_primeiro, 0), NULLIF(unanimidade_primeiro, 0)) < maioria_primeiro
               THEN 'unanime' ELSE 'maioria'
             END
      ELSE CASE
             WHEN GREATEST(unanime_ultimo, unanimidade_ultimo) > maioria_ultimo
             THEN 'unanime' ELSE 'maioria'
           END
    END AS deliberacao
  FROM votacao
),
/* A ordem é a regra: "negar provimento" contém "provimento", e "parcialmente
   provido" contém "provido". Sem padrão, nulo — nunca a categoria mais comum,
   que daria viés a um indicador feito para ser citado em petição. Dois recursos
   decididos ao contrário não têm UM resultado, então também ficam nulos. */
julgamento AS (
  SELECT
    fonte_codigo,
    identificador,
    CASE
      WHEN (SELECT COUNT(*) FROM REGEXP_MATCHES(texto, 'recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] ', 'g')) >= 2
       AND texto ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi'
       AND texto ~ '\md[aeo]\w*\s+(-lhe\s+)?provimento|deu-lhe\s+provimento|\mprovi[dm]' THEN NULL
      WHEN texto ~ 'parcial\w*\s+(provi|procedent)|provi\w*\s+(em\s+)?parte|provimento\s+parcial|acolh\w+\s+(em\s+)?parte|em\s+parte\s+provi'
        THEN 'parcialmente_provido'
      WHEN texto ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi|\mnao\s+conhec|\mrejeit|\mindeferi|\mnao\s+acolh|\mdenega'
        THEN 'negado'
      WHEN texto ~ '\md[aeo]\w*\s+provimento|\mprovi[dm]|\macolh|\mconced|\mdeferi'
        THEN 'provido'
    END AS resultado
  FROM dispositivo
),

montado AS (

SELECT
  b.fonte_codigo                                        AS fonte_codigo,
  b.identificador                                       AS identificador_fonte,
  b.identificador_documento                             AS identificador_documento,
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
  j.resultado                                           AS resultado,
  l.deliberacao                                         AS deliberacao,
  t.tese                                                AS tese,
  b.turma_recursal                                      AS turma_recursal,
  b.possui_inteiro_teor                                 AS possui_inteiro_teor,
  -- O número de registro identifica o PROCESSO, não o acórdão: um processo
  -- tem o acórdão original, os embargos, o agravo, e todos saem sob o mesmo
  -- registro. Sem a data de publicação, 12,2% das decisões do STJ dividiam a
  -- URL — até 27 no mesmo link — e quem clicava caía numa lista para escolher
  -- sozinho qual era a sua. Medido em 25/10/2026.
  --
  -- Com `dt_publicacao` o STJ devolve o PDF daquele acórdão em vez da lista:
  -- conferido contra o endpoint, 51 KB de PDF contra 41 KB de página HTML.
  -- Sobram 0,87%, que a tela avisa.
  --
  -- Sem data não dá para apontar, então o parâmetro inteiro sai do endereço:
  -- deixá-lo vazio mandaria o STJ procurar por uma data em branco. A expressão
  -- é genérica para valer em qualquer fonte que venha a usar um segundo token.
  CASE
    WHEN b.data_publicacao IS NULL
      THEN REPLACE(
        REGEXP_REPLACE(f.url_documento_template, '[?&][^?&=]+=\{publicacao\}', ''),
        '{documento}', b.identificador_documento
      )
    ELSE REPLACE(
      REPLACE(f.url_documento_template, '{documento}', b.identificador_documento),
      '{publicacao}', TO_CHAR(b.data_publicacao, 'DD/MM/YYYY')
    )
  END                                                   AS url_fonte,
  v.valido                                              AS link_valido,
  b.carga_id                                            AS carga_id,
  NOW()                                                 AS carregado_em,
  TO_TSVECTOR('portugues_sem_acento', b.ementa)         AS ementa_busca
FROM bruto AS b
JOIN core.fonte AS f ON f.codigo = b.fonte_codigo
LEFT JOIN verificacao.link AS v
  ON v.fonte_codigo = b.fonte_codigo
 AND v.identificador = b.identificador
LEFT JOIN tese AS t
  ON t.fonte_codigo = b.fonte_codigo
 AND t.identificador = b.identificador
LEFT JOIN lida AS l
  ON l.fonte_codigo = b.fonte_codigo
 AND l.identificador = b.identificador
LEFT JOIN julgamento AS j
  ON j.fonte_codigo = b.fonte_codigo
 AND j.identificador = b.identificador

)

SELECT
  m.*,
  -- Quando o link ainda alcança mais de uma decisão nossa, a tela precisa
  -- dizer isso: o leitor cai numa lista e tem de reconhecer a dele pela data,
  -- pelo órgão e pela classe. Calculado aqui porque é uma propriedade da
  -- coleção inteira, que nenhuma linha sabe sozinha.
  COUNT(*) OVER (PARTITION BY m.url_fonte) > 1           AS url_compartilhada
FROM montado AS m

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
