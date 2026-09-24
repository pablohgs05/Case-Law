CREATE SCHEMA core;
CREATE TYPE core.conhecimento AS ENUM (
    'conhecido',
    'parcialmente_conhecido',
    'nao_conhecido',
    'nao_identificado'
);
CREATE TYPE core.deliberacao AS ENUM (
    'unanime',
    'maioria',
    'nao_informado'
);
CREATE TYPE core.resultado AS ENUM (
    'provido',
    'parcialmente_provido',
    'desprovido',
    'prejudicado',
    'outro',
    'nao_identificado'
);
CREATE TYPE core.status_carga AS ENUM (
    'em_andamento',
    'concluida',
    'concluida_com_erros',
    'falhou'
);
CREATE TYPE core.status_fonte AS ENUM (
    'ativa',
    'cobertura_parcial',
    'indisponivel',
    'inativa'
);
CREATE TYPE core.tipo_texto AS ENUM (
    'ementa_completa',
    'trecho',
    'inteiro_teor'
);
CREATE FUNCTION core.sem_acento(t text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
    AS $$ SELECT public.unaccent('public.unaccent', t) $$;
CREATE TABLE core.carga (
    id bigint NOT NULL,
    fonte_codigo text NOT NULL,
    iniciada_em timestamp with time zone DEFAULT now() NOT NULL,
    concluida_em timestamp with time zone,
    status core.status_carga DEFAULT 'em_andamento'::core.status_carga NOT NULL,
    registros_lidos integer DEFAULT 0 NOT NULL,
    registros_gravados integer DEFAULT 0 NOT NULL,
    descartados_sigilo integer DEFAULT 0 NOT NULL,
    parametros jsonb,
    mensagem_erro text
);
CREATE SEQUENCE core.carga_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE core.carga_id_seq OWNED BY core.carga.id;
CREATE TABLE core.classe_processual (
    codigo_cnj integer NOT NULL,
    nome text
);
CREATE TABLE core.decisao (
    fonte_codigo text NOT NULL,
    identificador_fonte text NOT NULL,
    tribunal_sigla text NOT NULL,
    processo text,
    orgao_julgador text,
    relator text,
    classe_cnj integer,
    data_julgamento date,
    data_publicacao date,
    data_referencia date GENERATED ALWAYS AS (COALESCE(data_julgamento, data_publicacao)) STORED,
    ementa text NOT NULL,
    tipo_texto core.tipo_texto NOT NULL,
    decisao_texto text,
    conhecimento core.conhecimento,
    resultado core.resultado,
    deliberacao core.deliberacao,
    turma_recursal boolean DEFAULT false NOT NULL,
    possui_inteiro_teor boolean DEFAULT false NOT NULL,
    url_fonte text NOT NULL,
    carga_id bigint NOT NULL,
    carregado_em timestamp with time zone DEFAULT now() NOT NULL,
    ementa_busca tsvector GENERATED ALWAYS AS (to_tsvector('portuguese'::regconfig, core.sem_acento(ementa))) STORED,
    CONSTRAINT decisao_tem_data CHECK ((COALESCE(data_julgamento, data_publicacao) IS NOT NULL))
);
CREATE TABLE core.fonte (
    codigo text NOT NULL,
    nome text NOT NULL,
    tribunal_sigla text,
    url_base text NOT NULL,
    url_documento_template text NOT NULL,
    status core.status_fonte DEFAULT 'ativa'::core.status_fonte NOT NULL,
    cobertura_inicio date,
    cobertura_fim date,
    observacoes text
);
CREATE TABLE core.tribunal (
    sigla text NOT NULL,
    nome text NOT NULL,
    esfera text,
    uf character(2)
);
ALTER TABLE ONLY core.carga ALTER COLUMN id SET DEFAULT nextval('core.carga_id_seq'::regclass);
ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_pkey PRIMARY KEY (id);
ALTER TABLE ONLY core.classe_processual
    ADD CONSTRAINT classe_processual_pkey PRIMARY KEY (codigo_cnj);
ALTER TABLE ONLY core.decisao
    ADD CONSTRAINT decisao_pkey PRIMARY KEY (fonte_codigo, identificador_fonte);
ALTER TABLE ONLY core.fonte
    ADD CONSTRAINT fonte_pkey PRIMARY KEY (codigo);
ALTER TABLE ONLY core.tribunal
    ADD CONSTRAINT tribunal_pkey PRIMARY KEY (sigla);
CREATE INDEX carga_ultima_idx ON core.carga USING btree (fonte_codigo, concluida_em DESC) WHERE (status = 'concluida'::core.status_carga);
CREATE INDEX decisao_classe_idx ON core.decisao USING btree (classe_cnj);
CREATE INDEX decisao_data_idx ON core.decisao USING btree (data_referencia DESC, fonte_codigo, identificador_fonte);
CREATE INDEX decisao_ementa_idx ON core.decisao USING gin (ementa_busca);
CREATE INDEX decisao_orgao_idx ON core.decisao USING btree (tribunal_sigla, orgao_julgador);
CREATE INDEX decisao_processo_idx ON core.decisao USING btree (processo);
CREATE INDEX decisao_relator_idx ON core.decisao USING btree (tribunal_sigla, relator);
CREATE INDEX decisao_tribunal_idx ON core.decisao USING btree (tribunal_sigla, data_referencia DESC);
ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_fonte_codigo_fkey FOREIGN KEY (fonte_codigo) REFERENCES core.fonte(codigo);
ALTER TABLE ONLY core.decisao
    ADD CONSTRAINT decisao_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id);
ALTER TABLE ONLY core.decisao
    ADD CONSTRAINT decisao_classe_cnj_fkey FOREIGN KEY (classe_cnj) REFERENCES core.classe_processual(codigo_cnj);
ALTER TABLE ONLY core.decisao
    ADD CONSTRAINT decisao_fonte_codigo_fkey FOREIGN KEY (fonte_codigo) REFERENCES core.fonte(codigo);
ALTER TABLE ONLY core.decisao
    ADD CONSTRAINT decisao_tribunal_sigla_fkey FOREIGN KEY (tribunal_sigla) REFERENCES core.tribunal(sigla);
ALTER TABLE ONLY core.fonte
    ADD CONSTRAINT fonte_tribunal_sigla_fkey FOREIGN KEY (tribunal_sigla) REFERENCES core.tribunal(sigla);
