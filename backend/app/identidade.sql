-- Accounts, roles, and who added whom.
--
-- Deliberately outside `core`. Publishing the treated data runs
-- `DROP SCHEMA core CASCADE` and renames the staging schema over it, so an
-- account kept there would be destroyed on every publication — every manager
-- and every team, without a word. This schema is never touched by `publish`.

CREATE SCHEMA IF NOT EXISTS identidade;

CREATE TABLE IF NOT EXISTS identidade.usuario (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nome        TEXT        NOT NULL,
    telefone    TEXT,
    email       TEXT        NOT NULL,
    senha_hash  TEXT        NOT NULL,
    papel       TEXT        NOT NULL,
    -- Who added this account, which is the answer to "who let this person
    -- in" when two managers share the job. It bounds nothing: one firm
    -- uses this system, and every manager sees every account.
    gerente_id  UUID        REFERENCES identidade.usuario (id),
    ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revogado_em TIMESTAMPTZ,

    CONSTRAINT papel_conhecido CHECK (papel IN ('usuario', 'gerente')),

    -- A manager is added by the owner, out of band, and answers to nobody in
    -- the table. A common user always belongs to the manager who created them,
    -- so a user with no manager cannot exist and cannot be revoked by anyone.
    CONSTRAINT usuario_pertence_a_um_gerente CHECK (
        (papel = 'gerente' AND gerente_id IS NULL)
        OR (papel = 'usuario' AND gerente_id IS NOT NULL)
    ),

    -- Revoking is deactivating, never deleting: an account that searched has
    -- to stay readable. The date says when, and must be there when it happens.
    CONSTRAINT revogacao_tem_data CHECK (ativo OR revogado_em IS NOT NULL)
);

-- Case-insensitive on purpose. Nobody remembers whether they signed up with a
-- capital letter, and two rows on the same address are the same person.
CREATE UNIQUE INDEX IF NOT EXISTS usuario_email
    ON identidade.usuario (LOWER(email));

CREATE INDEX IF NOT EXISTS usuario_do_gerente
    ON identidade.usuario (gerente_id);
