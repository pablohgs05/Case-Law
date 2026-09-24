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
    turma_recursal       BOOLEAN NOT NULL,
    possui_inteiro_teor  BOOLEAN NOT NULL,
    url_fonte            TEXT    NOT NULL,
    link_valido          BOOLEAN,
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

INSERT INTO core.fonte VALUES (
    'tjdft-jurisdf', 'TJDFT JurisDF', 'TJDFT',
    'https://jurisdf.tjdft.jus.br/detalhes/{identificador}'
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
    identificador TEXT        PRIMARY KEY,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
