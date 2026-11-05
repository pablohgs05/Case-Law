-- What the model read out of a decision, kept because reading it again costs
-- money and a quota.
--
-- Deliberately outside `core`, for the same reason `identidade` is: publishing
-- the treated data runs `DROP SCHEMA core CASCADE` and renames the staging
-- schema over it. A reading kept there would be thrown away on every
-- publication and paid for a second time, silently.

CREATE SCHEMA IF NOT EXISTS leitura;

CREATE TABLE IF NOT EXISTS leitura.tese (
    fonte_codigo        TEXT        NOT NULL,
    identificador_fonte TEXT        NOT NULL,

    tese                TEXT        NOT NULL,

    -- The passage the thesis was drawn from, copied from the ementa word for
    -- word. Nothing is stored before this string is found in the ementa, so a
    -- row here is a reading that was checked, never one that was trusted.
    trecho              TEXT        NOT NULL,

    -- Which model wrote it. A reading made by an older model stays readable
    -- and stays attributable; without this, replacing the model would quietly
    -- mix two different readings in the same table.
    modelo              TEXT        NOT NULL,

    -- The ementa this was read from. The published collection is rebuilt from
    -- the sources, and an ementa can change between publications — when it
    -- does, the reading no longer describes the text on screen and has to be
    -- made again rather than shown.
    ementa_digest       TEXT        NOT NULL,

    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (fonte_codigo, identificador_fonte)
);
