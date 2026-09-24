-- Runs once, the first time the database is created.
-- Dropping the volume and bringing the service up again replays it.

-- Similarity search that tolerates typing errors: "usucapiao" finds "usucapião".
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Makes accents irrelevant when searching: "acao" finds "ação".
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Vector column and distance operators, used by semantic search later on.
CREATE EXTENSION IF NOT EXISTS vector;

-- Portuguese search that folds accents inside the dictionary instead of on the
-- text. Searching "acao" still finds "ação", and the highlighted snippet keeps
-- the accents the court actually wrote.
CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento ( COPY = portuguese );
ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;

-- Whether each decision's link still reaches a document at the court.
-- Written by `pipeline/verify_links.py`, read by the core model. Declared here
-- so the transformation builds on a database nobody has verified yet: a record
-- with no row is unverified, which is not the same as invalid.
CREATE SCHEMA IF NOT EXISTS verificacao;
CREATE TABLE IF NOT EXISTS verificacao.link (
    identificador TEXT        PRIMARY KEY,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
