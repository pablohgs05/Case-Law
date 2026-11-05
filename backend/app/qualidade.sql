-- Reports of a classification a reader believes is wrong.
--
-- Deliberately outside `core`, for the reason `identidade` is: publishing the
-- treated data runs `DROP SCHEMA core CASCADE` and renames the staging schema
-- over it, so a report kept there would vanish on the next publication —
-- exactly the moment someone would go looking for it. Nothing here points into
-- `core` with a foreign key, for the same reason: the decision is named by the
-- pair the collection itself uses, which survives a republication.
--
-- Applied after `identidade.sql`: a report belongs to the account that sent it.

CREATE SCHEMA IF NOT EXISTS qualidade;

CREATE TABLE IF NOT EXISTS qualidade.reporte (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fonte_codigo        TEXT        NOT NULL,
    identificador_fonte TEXT        NOT NULL,
    -- Which of the tool's readings is contested.
    informacao          TEXT        NOT NULL,
    -- What the tool was publishing when the report arrived. The classification
    -- can change with the next publication, and a report read without it no
    -- longer says what the reader disagreed with. NULL when there was nothing
    -- published for that information.
    valor_publicado     TEXT,
    relato              TEXT        NOT NULL,
    usuario_id          UUID        NOT NULL REFERENCES identidade.usuario (id),
    -- A report is a request for review, never a correction: it arrives
    -- pending, and nothing in this schema writes back into the classification.
    situacao            TEXT        NOT NULL DEFAULT 'pendente',
    -- The instant the row is written, not the start of its transaction: two
    -- reports sent together still come back in the order they were sent.
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT CLOCK_TIMESTAMP(),

    CONSTRAINT informacao_conhecida CHECK (
        informacao IN ('resultado', 'deliberacao', 'aderencia', 'tese')
    ),
    CONSTRAINT situacao_conhecida CHECK (
        situacao IN ('pendente', 'aceito', 'recusado')
    ),
    CONSTRAINT relato_tem_conteudo CHECK (
        LENGTH(BTRIM(relato)) BETWEEN 1 AND 2000
    )
);

-- The manager's list reads newest first.
CREATE INDEX IF NOT EXISTS reporte_recentes
    ON qualidade.reporte (criado_em DESC);

CREATE INDEX IF NOT EXISTS reporte_da_decisao
    ON qualidade.reporte (fonte_codigo, identificador_fonte);
