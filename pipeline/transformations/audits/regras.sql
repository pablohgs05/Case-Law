AUDIT (
  name sem_segredo_de_justica,
  dialect postgres
);
/* Nenhuma decisão em segredo de justiça pode chegar ao núcleo.
   O filtro está na transformação; esta auditoria é a rede de segurança. */
SELECT d.*
FROM @this_model AS d
JOIN raw.acordao_tjdft AS r
  ON r.identificador = d.identificador_fonte
WHERE COALESCE(r."segredoJustica", FALSE);

AUDIT (
  name data_referencia_preenchida,
  dialect postgres
);
/* Documento sem nenhuma data não é filtrável nem ordenável — não serve ao produto. */
SELECT * FROM @this_model WHERE data_referencia IS NULL;

AUDIT (
  name data_do_stj_convertida,
  dialect postgres
);
/* dataDecisao chega como texto YYYYMMDD. Mudou o formato, TO_DATE devolve NULL
   calado e a decisão some do filtro por período em vez de dar erro. */
SELECT d.*
FROM @this_model AS d
JOIN raw.espelho_stj AS r
  ON r.id = d.identificador_fonte
WHERE d.fonte_codigo = 'stj-espelhos'
  AND COALESCE(TRIM(r."dataDecisao"), '') <> ''
  AND d.data_julgamento IS NULL;

AUDIT (
  name url_carrega_o_identificador,
  dialect postgres
);
/* O link sai do template do seed por REPLACE. Se o template perder o
   {documento}, nada falha: a fonte inteira passa a apontar para a mesma página.
   O token não é a chave do registro: o TJDFT abre o acórdão pelo uuid, o STJ
   pelo próprio id. */
SELECT *
FROM @this_model
WHERE POSITION(identificador_documento IN url_fonte) = 0;

AUDIT (
  name ementa_nao_vazia,
  dialect postgres
);
/* not_null não pega string vazia. Ementa vazia é resultado sem texto na tela e
   sem nada para o índice de busca. */
SELECT *
FROM @this_model
WHERE TRIM(ementa) = '';

AUDIT (
  name token_do_documento_por_fonte,
  dialect postgres
);
/* Trocar a chave não quebra nada visível: a URL continua bem formada e o site
   responde 200. Nenhuma fonte abre pelo identificador do registro, então a
   primeira condição pega a troca em toda a coleção de uma vez. O formato só é
   exigido do TJDFT: o STJ publica alguns números de registro quebrados, e
   reprovar a carga por isso esconderia decisão real. */
SELECT *
FROM @this_model
WHERE identificador_documento = identificador_fonte
   OR (
     fonte_codigo = 'tjdft-jurisdf'
     AND identificador_documento !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   );

AUDIT (
  name verdito_de_fonte_conhecida,
  dialect postgres
);
/* Veredicto sob código de fonte inexistente fica órfão: não casa com nada, não
   dá erro, e a decisão fica sem verificação para sempre. */
SELECT v.*
FROM verificacao.link AS v
LEFT JOIN core.fonte AS f
  ON f.codigo = v.fonte_codigo
WHERE f.codigo IS NULL
  AND EXISTS (SELECT 1 FROM @this_model);

AUDIT (
  name deliberacao_de_valor_conhecido,
  dialect postgres
);
/* Valor que a tela não traduz não dá erro: ela mostra em branco. */
SELECT *
FROM @this_model
WHERE deliberacao IS NOT NULL
  AND deliberacao NOT IN ('unanime', 'maioria');

AUDIT (
  name deliberacao_com_cobertura,
  dialect postgres
);
/* Se o tribunal mudar a redação a expressão para de casar e a coluna fica nula
   em silêncio. O piso é sobre quem TEM dispositivo, e só a partir de 100 mil
   linhas, senão todo ambiente de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(deliberacao) < COUNT(*) * 0.95;

AUDIT (
  name resultado_de_valor_conhecido,
  dialect postgres
);
/* Valor que a tela não traduz não dá erro: ela mostra em branco. */
SELECT *
FROM @this_model
WHERE resultado IS NOT NULL
  AND resultado NOT IN ('provido', 'parcialmente_provido', 'negado');

AUDIT (
  name resultado_com_cobertura,
  dialect postgres
);
/* Se o tribunal mudar a redação a expressão para de casar e a coluna fica nula
   em silêncio. O piso é sobre quem TEM dispositivo, e só a partir de 100 mil
   linhas, senão todo ambiente de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(resultado) < COUNT(*) * 0.90;

AUDIT (
  name resultado_sem_contradicao,
  dialect postgres
);
/* Os padrões se contêm, então a ordem da cascata é a regra — e trocá-la não
   quebra nada visível, só erra o rótulo. Aqui cada rótulo é confrontado com o
   padrão que tem prioridade sobre ele. */
SELECT *
FROM @this_model
WHERE resultado IS NOT NULL
  AND (
    (resultado = 'provido'
     AND UNACCENT(LOWER(decisao_texto)) ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi|\mnao\s+conhec|\mrejeit|\mindeferi|\mnao\s+acolh|\mdenega')
    OR (resultado <> 'parcialmente_provido'
     AND UNACCENT(LOWER(decisao_texto)) ~ 'parcial\w*\s+(provi|procedent)|provi\w*\s+(em\s+)?parte|provimento\s+parcial|acolh\w+\s+(em\s+)?parte|em\s+parte\s+provi')
    OR ((SELECT COUNT(*) FROM REGEXP_MATCHES(UNACCENT(LOWER(decisao_texto)), 'recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] ', 'g')) >= 2
     AND UNACCENT(LOWER(decisao_texto)) ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi'
     AND UNACCENT(LOWER(decisao_texto)) ~ '\md[aeo]\w*\s+(-lhe\s+)?provimento|deu-lhe\s+provimento|\mprovi[dm]')
  );

AUDIT (
  name classe_de_codigo_conhecido,
  dialect postgres
);
/* A ponte do STJ é um join por nome. Código que não existe na tabela significa
   que a semente andou sem o modelo, e a tela mostra um filtro que não filtra. */
SELECT d.*
FROM @this_model AS d
LEFT JOIN core.classe_processual AS c ON c.codigo_cnj = d.classe_cnj
WHERE d.classe_cnj IS NOT NULL
  AND c.codigo_cnj IS NULL;

AUDIT (
  name classe_com_cobertura,
  dialect postgres
);
/* O STJ escreve a classe por extenso e já manda quebra de linha no meio. Se a
   grafia mudar, o join para de casar e a coluna fica nula em silêncio: o filtro
   encolhe sem avisar. Só vale a partir de 100 mil linhas, senão todo ambiente
   de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 100000
   AND COUNT(classe_cnj) < COUNT(*) * 0.95;

AUDIT (
  name precedente_de_corte_conhecida,
  dialect postgres
);
/* Súmula 7 do STJ e Súmula 7 do STF são precedentes diferentes. Uma linha sem
   corte declarada colidiria com a outra na chave. */
SELECT *
FROM @this_model
WHERE corte NOT IN ('STJ', 'STF');

AUDIT (
  name precedente_com_enunciado,
  dialect postgres
);
/* O enunciado é o produto: sem ele, sobra a contagem de citações, que é outra
   história. Um recorte que pegou pontuação em vez de texto cai aqui. */
SELECT *
FROM @this_model
WHERE LENGTH(BTRIM(COALESCE(enunciado, ''))) < 40;

AUDIT (
  name precedente_com_volume,
  dialect postgres
);
/* Se o tribunal mudar a forma de transcrever, o recorte para de casar e a
   tabela encolhe em silêncio — a tela mostraria menos precedentes sem avisar.
   As duas origens degradam por motivos diferentes — o tribunal muda a forma de
   transcrever, ou o portal muda o CSV —, então cada uma tem o próprio piso.
   Hoje: 371 súmulas reconstruídas e 1.142 temas do catálogo. */
SELECT 1 AS falha
FROM @this_model
GROUP BY origem
HAVING (origem = 'reconstruido' AND COUNT(*) < 300)
    OR (origem = 'catalogo' AND COUNT(*) < 1000);

AUDIT (
  name citacao_de_tipo_conhecido,
  dialect postgres
);
/* Tipo fora da lista não casa com core.precedente: órfã, e sem erro. */
SELECT *
FROM @this_model
WHERE tipo NOT IN ('sumula', 'tema')
   OR corte NOT IN ('STJ', 'STF');

AUDIT (
  name citacao_com_volume,
  dialect postgres
);
/* Redação muda, extração encolhe calada: o indicador mediria menos acervo. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) < 300000;

AUDIT (
  name aderencia_de_valor_conhecido,
  dialect postgres
);
/* Texto cru vazando de uma captura de grupo chega aqui. `indeterminado` é
   valor, não ausência: numa ferramenta jurídica "não sei" é resposta. */
SELECT *
FROM @this_model
WHERE aderencia NOT IN
  ('seguiu', 'afastou', 'distinguiu', 'mencionou', 'indeterminado');

AUDIT (
  name aderencia_sem_contradicao,
  dialect postgres
);
/* "nao se aplica" contém "aplica": trocar a ordem da cascata não quebra nada
   visível, só inverte o rótulo. */
SELECT *
FROM @this_model
WHERE aderencia IN ('seguiu', 'distinguiu')
  AND trecho ~ 'nao\s+(se\s+)?(aplica|incid|atrai)|inaplica|superad[oa]|nao\s+obsta|nao\s+ha\s+falar\s+em\s+(aplicacao|incidencia)|afastad\w*\s+(a\s+|o\s+)?(incidencia|aplicacao|obice)';

AUDIT (
  name aderencia_com_cobertura,
  dialect postgres
);
/* Conta quem foi decidido, não quem tem valor: toda linha tem valor desde que
   `indeterminado` virou categoria, e contar não-nulo daria sempre 100%. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 100000
   AND COUNT(*) FILTER (WHERE aderencia <> 'indeterminado') < COUNT(*) * 0.65;

AUDIT (
  name citacao_resolvida_com_precedente,
  dialect postgres
);
/* `resolvida` é a promessa de que a tela consegue mostrar o enunciado. Catálogo
   coletado pela metade deixaria ligação órfã marcada como resolvida, e o leitor
   veria a citação de um precedente que o sistema não sabe exibir.
   Numa direção só: a ligação sem corte declarada não resolve mesmo havendo
   linha de mesmo número no catálogo, porque seria o precedente de outra corte. */
SELECT dp.*
FROM @this_model AS dp
LEFT JOIN core.precedente AS p
  ON p.corte = dp.corte AND p.tipo = dp.tipo AND p.numero = dp.numero
WHERE dp.resolvida AND p.corte IS NULL;

AUDIT (
  name citacao_com_alcance,
  dialect postgres
);
/* Se a redação das citações mudar, a extração encolhe calada e a tela diz
   "nenhum precedente citado" para o acervo inteiro, com aparência de normal.
   O piso é sobre a proporção de decisões, não de ligações: hoje 30,2%. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(DISTINCT (fonte_codigo, identificador_fonte))
     < (SELECT COUNT(*) FROM core.decisao) * 0.24;

AUDIT (
  name citacao_com_corte_do_texto,
  dialect postgres
);
/* A corte é metade da identidade do precedente, e atribuí-la por constante
   fez 11.252 citações exibirem o enunciado de outro. Nenhuma ligação pode
   afirmar STF sem que a ementa diga STF ou repercussão geral. */
SELECT dp.*
FROM @this_model AS dp
JOIN core.decisao AS d
  ON d.fonte_codigo = dp.fonte_codigo
 AND d.identificador_fonte = dp.identificador_fonte
WHERE dp.corte_declarada
  AND dp.corte = 'STF'
  /* Os espaços são colapsados como no modelo: "repercussão\ngeral" partida em
     duas linhas escapa de um padrão que espera um espaço só. */
  AND UNACCENT(LOWER(REGEXP_REPLACE(d.ementa, '\s+', ' ', 'g')))
      !~ 'stf|supremo|repercussao geral';

AUDIT (
  name tese_sem_secao_seguinte,
  dialect postgres
);
/* O bloco da tese termina onde começa a lista de citações. Arrastá-la não dá
   erro: a coluna fica preenchida, o card enche de referências de acórdão e a
   tese some no meio. Só aparece olhando a tela. */
SELECT *
FROM @this_model
WHERE tese IS NOT NULL
  AND tese ~* '(Dispositivos?[[:space:]]+relevantes?|Jurisprud[eê]ncia[[:space:]]+relevante)';

AUDIT (
  name tese_com_cobertura,
  dialect postgres
);
/* No dia em que o rótulo mudar de redação, a extração para de casar e a coluna
   fica nula em silêncio — a tela mostra "sem tese" para a coleção inteira, com
   aparência de funcionamento normal. O piso é 4%: medido em 5,6% sobre
   984.824 decisões, e a tendência sobe porque o padrão do CNJ é de 2024.

   O piso só vale a partir de 100 mil linhas. Porcentagem não distingue "a
   extração quebrou" de "esta tabela é uma amostra": num ambiente com dez
   registros de desenvolvimento a cobertura é zero e isso é o esperado, não
   defeito. Sem essa condição a auditoria reprova todo ambiente que não seja o
   de produção, e quem a vê falhar aprende a ignorá-la. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 100000
   AND COUNT(*) FILTER (WHERE tese IS NOT NULL) < COUNT(*) * 0.04;

AUDIT (
  name doutrina_de_acesso_aberto,
  dialect postgres
);
/* O escopo da história, executável. A coleção é a garantia: o STJ separou
   Acesso Aberto de Acesso Restrito, e só a primeira entra. Onde `dc:rights`
   aparece — 5,8% dos registros — ele manda, e é lista de permissão: um
   registro arquivado em Acesso Aberto declarou "Restricted access" no próprio
   campo, 1 em 798 na amostra, e ficou de fora. Direitos desconhecido exclui a
   obra em vez de incluí-la. */
SELECT *
FROM @this_model
WHERE NOT ('col_2011_8' = ANY (conjuntos))
   OR 'col_2011_9' = ANY (conjuntos)
   OR (direitos IS NOT NULL AND direitos !~* 'acesso aberto|open access');

AUDIT (
  name doutrina_com_titulo,
  dialect postgres
);
/* Obra sem título não é apontável: a tela mostraria uma linha em branco com
   link. O recorte do bloco `oai_dc` é por expressão regular, então um título
   vazio significa que o recorte pegou outra coisa, não que a biblioteca
   catalogou sem título. */
SELECT *
FROM @this_model
WHERE COALESCE(BTRIM(titulo), '') = ''
   OR titulo !~ '[[:alpha:]]';

AUDIT (
  name doutrina_com_link_do_acervo,
  dialect postgres
);
/* `dc:identifier` aparece duas, três ou quatro vezes no mesmo registro: a
   referência bibliográfica, um ISSN e o link permanente dividem a mesma tag.
   Pegar o primeiro valor põe a referência onde devia estar o link, e o erro
   não aparece até alguém clicar. O handle do link tem de ser o mesmo número do
   identificador OAI — 798 de 798 conferem hoje. */
SELECT *
FROM @this_model
WHERE url_fonte NOT LIKE 'https://bdjur.stj.jus.br/handle/%'
   OR url_fonte <> 'https://bdjur.stj.jus.br/handle/' || SPLIT_PART(identificador_oai, ':', 3);

AUDIT (
  name doutrina_sem_texto_integral,
  dialect postgres
);
/* Metadado e link, nunca a obra. Acesso aberto é permissão de ler, não de
   redistribuir, e é a diferença entre apontar doutrina e republicá-la. O teto
   de 5.000 caracteres não julga resumo comprido: ele reprova o dia em que
   alguém apontar o extrator para o texto da obra e gravá-lo aqui. O maior
   `dc:description` da amostra tem 1.255 caracteres, a média 219. O link
   também precisa levar ao registro, não ao arquivo. */
SELECT *
FROM @this_model
WHERE LENGTH(resumo) > 5000
   OR url_fonte ~* '\.(pdf|doc|docx|rtf|epub)$';

AUDIT (
  name doutrina_com_ano_plausivel,
  dialect postgres
);
/* O primeiro `dc:date` de todos os 798 registros é a entrada no acervo, não a
   publicação: uma obra de 1976 digitalizada em 2019 traz as duas datas na
   mesma tag. Trocar uma pela outra não dá erro — enche a coluna de anos
   recentes e ordena a lista pela data de digitalização. Ano fora da faixa é o
   sintoma. Nulo não reprova: a biblioteca às vezes não registrou. */
SELECT *
FROM @this_model
WHERE ano IS NOT NULL
  AND (ano < 1900 OR ano > EXTRACT(YEAR FROM NOW()) + 1);

AUDIT (
  name doutrina_com_cobertura_de_assunto,
  dialect postgres
);
/* Assunto é por onde a doutrina casa com a decisão, e `dc:subject` é
   opcional: 54,8% dos registros o trazem. Se a extração quebrar, a coluna fica
   vazia em silêncio e a tela passa a não achar doutrina nenhuma, com cara de
   acervo sem obra sobre o tema. O piso é 30%, e só vale a partir de 500
   linhas: num ambiente de desenvolvimento com dez registros a cobertura é
   zero e isso é o esperado. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 500
   AND COUNT(*) FILTER (WHERE CARDINALITY(assuntos) > 0) < COUNT(*) * 0.30;

AUDIT (
  name termo_de_obra_existente,
  dialect postgres
);
/* Termo sob identificador que não existe em core.doutrina fica órfão: não casa
   com nada, não aparece em lugar nenhum, e some da conta sem avisar. */
SELECT t.*
FROM @this_model AS t
LEFT JOIN core.doutrina AS d
  ON d.repositorio = t.repositorio
 AND d.identificador_oai = t.identificador_oai
WHERE d.identificador_oai IS NULL;

AUDIT (
  name termo_acima_do_piso,
  dialect postgres
);
/* O piso é o que faz a sugestão falar de assunto. Abaixo de 2,0 está a palavra
   presente em mais de 13% das decisões — `prova`, `súmula`, `direito` —, que
   casa qualquer tese com qualquer obra. Radical de três letras é acidente do
   radicalizador: `via` liga "via adequada" a "terceira via". */
SELECT *
FROM @this_model
WHERE peso < 2.0
   OR LENGTH(termo) < 4;

AUDIT (
  name termo_com_cobertura,
  dialect postgres
);
/* Se a construção do vetor de busca quebrar, esta tabela encolhe e a tela
   passa a não sugerir doutrina nenhuma, com cara de acervo sem obra sobre o
   tema. Hoje são 10.032 pares sobre 797 obras — 12,6 termos por obra, de 3.569
   distintos. O piso é de 5 termos por obra, e só vale a partir de 100 obras,
   para um ambiente de desenvolvimento com três registros não reprovar. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(DISTINCT identificador_oai) > 100
   AND COUNT(*) < COUNT(DISTINCT identificador_oai) * 5;

AUDIT (
  name sugestao_de_decisao_com_tese,
  dialect postgres
);
/* Sem tese não há do que casar. Sugestão para decisão sem tese significa que o
   casamento passou a usar outro campo — a ementa inteira, por exemplo — e o
   resultado fica mais grosseiro sem que nada falhe. */
SELECT s.*
FROM @this_model AS s
LEFT JOIN core.decisao AS d
  ON d.fonte_codigo = s.fonte_codigo
 AND d.identificador_fonte = s.identificador_fonte
WHERE d.identificador_fonte IS NULL
   OR d.tese IS NULL;

AUDIT (
  name sugestao_de_obra_existente,
  dialect postgres
);
/* Obra inexistente vira link quebrado na tela: a decisão diz que há doutrina
   relacionada e o leitor clica em nada. */
SELECT s.*
FROM @this_model AS s
LEFT JOIN core.doutrina AS d
  ON d.repositorio = s.repositorio
 AND d.identificador_oai = s.identificador_oai
WHERE d.identificador_oai IS NULL;

AUDIT (
  name sugestao_acima_do_limite,
  dialect postgres
);
/* A regra que protege o leitor, executável. O limite não é preferência de
   apresentação: é o que separa sugestão de chute, e baixá-lo sem remedir a
   taxa de acerto enche a tela de obra sobre outro assunto com aparência de
   relacionada. Quem mexer nos números tem de mexer aqui também. */
SELECT *
FROM @this_model
WHERE nota < 9.0
   OR termos < 2
   OR termo_mais_forte < 4.5
   OR distancia IS NULL
   OR distancia > 8;

AUDIT (
  name sugestao_com_termo_proprio,
  dialect postgres
);
/* `casou_em` é o que a tela mostra para justificar a sugestão, e tem de conter
   o termo que a sustenta. Lista vazia, ou com menos termos do que a contagem
   diz, é sugestão sem como responder por si. */
SELECT *
FROM @this_model
WHERE casou_em IS NULL
   OR CARDINALITY(casou_em) <> termos;

AUDIT (
  name sugestao_com_cobertura,
  dialect postgres
);
/* O limite cala quando não sabe, então esta tabela é pequena de propósito —
   26,9% das 57.439 decisões com tese. Mas zero não é "limite rigoroso", é
   casamento quebrado, e a diferença não aparece na tela: as duas mostram
   "nenhuma doutrina relacionada". O piso é 5% das decisões com tese, e só vale
   a partir de mil teses. */
SELECT 1 AS falha
FROM core.decisao
HAVING COUNT(*) FILTER (WHERE tese IS NOT NULL) > 1000
   AND (SELECT COUNT(DISTINCT identificador_fonte) FROM @this_model)
       < COUNT(*) FILTER (WHERE tese IS NOT NULL) * 0.05;

AUDIT (
  name url_aponta_para_um_acordao,
  dialect postgres
);
/* O link oficial tem de levar ao acórdão que o leitor estava lendo.

   O número de registro do STJ identifica o processo, não o julgamento: o
   acórdão original, os embargos de declaração e o agravo interno saem todos
   sob o mesmo registro. Antes da data de publicação entrar no endereço,
   107.128 decisões — 12,2% do STJ, até 27 no mesmo link — mandavam o leitor
   para uma página de lista escolher qual era a sua. Numa ferramenta jurídica
   citar o acórdão errado é grave, e era o contrário do que o projeto promete.

   A auditoria da SCRUM-94 não pegava isso: ela confere que a URL carrega o
   identificador, e carregava. O que faltava era conferir que o identificador
   alcança um documento só.

   O piso é 2% do acervo com link. Hoje são 0,87%, resto que a data de
   publicação não resolve porque o STJ publicou dois julgamentos do mesmo
   processo no mesmo diário. Esses a tela avisa, em vez de calar.

   Só vale a partir de dez mil decisões: num ambiente de desenvolvimento com
   três registros a porcentagem não diz nada. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) FILTER (WHERE url_fonte IS NOT NULL) > 10000
   AND COUNT(*) FILTER (WHERE url_compartilhada)
       > COUNT(*) FILTER (WHERE url_fonte IS NOT NULL) * 0.02;
