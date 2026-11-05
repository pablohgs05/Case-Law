CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS vector;

DROP TEXT SEARCH CONFIGURATION IF EXISTS portugues_sem_acento;
CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento ( COPY = portuguese );
ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;

DROP SCHEMA IF EXISTS core CASCADE;
CREATE SCHEMA core;

CREATE TABLE core.decisao (
    fonte_codigo         TEXT    NOT NULL,
    identificador_fonte  TEXT    NOT NULL,
    tribunal_sigla       TEXT    NOT NULL,
    processo             TEXT,
    orgao_julgador       TEXT,
    relator              TEXT,
    classe_cnj           BIGINT,
    data_julgamento      DATE,
    data_publicacao      DATE,
    data_referencia      DATE    NOT NULL,
    ementa               TEXT    NOT NULL,
    tipo_texto           TEXT,
    decisao_texto        TEXT,
    tese                 TEXT,
    resultado            TEXT,
    deliberacao          TEXT,
    turma_recursal       BOOLEAN NOT NULL,
    possui_inteiro_teor  BOOLEAN NOT NULL,
    url_fonte            TEXT    NOT NULL,
    link_valido          BOOLEAN,
    url_compartilhada    BOOLEAN NOT NULL DEFAULT FALSE,
    ementa_busca         TSVECTOR
);

CREATE UNIQUE INDEX ON core.decisao (fonte_codigo, identificador_fonte);
CREATE INDEX ON core.decisao USING gin (ementa_busca);

CREATE TABLE core.fonte (
    codigo                 TEXT NOT NULL,
    nome                   TEXT NOT NULL,
    tribunal_sigla         TEXT NOT NULL,
    url_documento_template TEXT NOT NULL
);

INSERT INTO core.fonte VALUES
('tjdft-jurisdf', 'TJDFT JurisDF', 'TJDFT',
 'https://jurisdf.tjdft.jus.br/acordaos/{documento}'),
('stj-espelhos', 'STJ Espelhos de Acórdãos', 'STJ',
 'https://processo.stj.jus.br/processo/revista/documento/mediado/?componente=ITA&sequencial={documento}');

-- The same row as pipeline/transformations/seeds/tribunal.csv.
CREATE TABLE core.tribunal (
    sigla  TEXT NOT NULL PRIMARY KEY,
    nome   TEXT NOT NULL,
    esfera TEXT,
    uf     TEXT
);

INSERT INTO core.tribunal VALUES (
    'TJDFT', 'Tribunal de Justiça do Distrito Federal e dos Territórios',
    'distrital', 'DF'
);

-- Written by the pipeline's link check, read by the core model.
DROP SCHEMA IF EXISTS verificacao CASCADE;
CREATE SCHEMA verificacao;
CREATE TABLE core.carga (
    carga_id              TEXT        NOT NULL,
    fonte_codigo          TEXT        NOT NULL,
    concluida_em          TIMESTAMPTZ NOT NULL,
    status                TEXT        NOT NULL,
    registros_lidos       BIGINT      NOT NULL,
    registros_gravados    BIGINT      NOT NULL,
    descartados_sigilo    BIGINT      NOT NULL,
    links_invalidos       BIGINT      NOT NULL,
    links_nao_verificados BIGINT      NOT NULL
);

-- Two successful loads, so a test can tell "the most recent" from "any", and a
-- failed one dated after both: if the endpoint ever sorts before filtering, the
-- failure becomes the answer and the tests say so.
INSERT INTO core.carga VALUES
('1789000000.0', 'tjdft-jurisdf', '2026-03-16 02:00:00+00', 'concluida', 6, 4, 2, 0, 4),
('1789000001.0', 'tjdft-jurisdf', '2026-03-17 02:00:00+00', 'concluida', 9, 9, 0, 0, 9),
('1789000002.0', 'tjdft-jurisdf', '2026-03-18 02:00:00+00', 'falhou',    0, 0, 0, 0, 0);

CREATE TABLE verificacao.link (
    fonte_codigo  TEXT        NOT NULL,
    identificador TEXT        NOT NULL,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fonte_codigo, identificador)
);

-- A amostra da tabela do CNJ que a transformação consulta. Traz de propósito
-- "Ação Rescisória" em dois códigos, um deles sob a árvore do STJ, para que o
-- desempate por raiz seja exercitado em vez de assumido.
CREATE TABLE core.classe_processual (
    codigo_cnj BIGINT NOT NULL PRIMARY KEY,
    codigo_pai BIGINT,
    nome       TEXT   NOT NULL
);

INSERT INTO core.classe_processual VALUES
(2,     NULL, 'PROCESSO CÍVEL E DO TRABALHO'),
(5,     NULL, 'SUPERIOR TRIBUNAL DE JUSTIÇA'),
(47,    2,    'Ação Rescisória'),
(1669,  5,    'Ação Rescisória'),
(198,   2,    'Apelação Cível'),
(213,   5,    'Recurso Especial'),
(1321,  5,    'Agravo Regimental'),
(1331,  5,    'Habeas Corpus');

CREATE TABLE core.precedente (
    corte        TEXT   NOT NULL,
    tipo         TEXT   NOT NULL,
    numero       BIGINT NOT NULL,
    enunciado    TEXT   NOT NULL,
    situacao     TEXT,
    data         DATE,
    url_fonte    TEXT,
    origem       TEXT   NOT NULL,
    transcricoes BIGINT,
    carregado_em TIMESTAMPTZ,
    PRIMARY KEY (corte, tipo, numero)
);

CREATE TABLE core.decisao_precedente (
    fonte_codigo        TEXT   NOT NULL,
    identificador_fonte TEXT   NOT NULL,
    corte               TEXT   NOT NULL,
    tipo                TEXT   NOT NULL,
    numero              BIGINT NOT NULL,
    trecho              TEXT   NOT NULL,
    resolvida           BOOLEAN NOT NULL,
    corte_declarada     BOOLEAN NOT NULL DEFAULT TRUE,
    aderencia           TEXT   NOT NULL,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte, corte, tipo, numero)
);

CREATE TABLE core.doutrina (
    repositorio          TEXT NOT NULL,
    identificador_oai    TEXT NOT NULL,
    titulo               TEXT NOT NULL,
    titulos_alternativos TEXT[] NOT NULL DEFAULT '{}',
    autores              TEXT[] NOT NULL DEFAULT '{}',
    assuntos             TEXT[] NOT NULL DEFAULT '{}',
    tipo                 TEXT,
    data                 TEXT,
    ano                  BIGINT,
    idioma               TEXT,
    publicacao           TEXT,
    resumo               TEXT,
    referencia           TEXT,
    url_fonte            TEXT NOT NULL,
    direitos             TEXT,
    conjuntos            TEXT[] NOT NULL DEFAULT '{}',
    arquivada_em         TIMESTAMPTZ,
    alterada_em          TIMESTAMPTZ,
    busca                TSVECTOR,
    carregado_em         TIMESTAMPTZ,
    PRIMARY KEY (repositorio, identificador_oai)
);

CREATE INDEX ON core.doutrina USING gin (busca);

CREATE TABLE core.decisao_doutrina (
    fonte_codigo        TEXT NOT NULL,
    identificador_fonte TEXT NOT NULL,
    repositorio         TEXT NOT NULL,
    identificador_oai   TEXT NOT NULL,
    nota                DOUBLE PRECISION NOT NULL,
    termos              BIGINT NOT NULL,
    termo_mais_forte    DOUBLE PRECISION NOT NULL,
    casou_em            TEXT[] NOT NULL,
    distancia           INTEGER NOT NULL,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte, repositorio, identificador_oai)
);

CREATE TABLE core.doutrina_termo (
    repositorio       TEXT NOT NULL,
    identificador_oai TEXT NOT NULL,
    termo             TEXT NOT NULL,
    decisoes          BIGINT NOT NULL,
    peso              DOUBLE PRECISION NOT NULL,
    carregado_em      TIMESTAMPTZ,
    PRIMARY KEY (repositorio, identificador_oai, termo)
);

-- Dropped here, created by `app/identidade.sql`: the accounts schema has one
-- definition, and a copy of it here would be a copy that drifts.
DROP SCHEMA IF EXISTS identidade CASCADE;
