DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

CREATE TABLE raw.acordao_tjdft (
    identificador            TEXT,
    uuid                     TEXT,
    "dataJulgamento"         TIMESTAMPTZ,
    "dataPublicacao"         TIMESTAMPTZ,
    processo                 TEXT,
    "descricaoOrgaoJulgador" TEXT,
    "nomeRelator"            TEXT,
    "codigoClasseCnj"        BIGINT,
    ementa                   TEXT,
    decisao                  TEXT,
    "turmaRecursal"          BOOLEAN,
    "possuiInteiroTeor"      BOOLEAN,
    "segredoJustica"         BOOLEAN,
    _dlt_load_id             TEXT
);

INSERT INTO raw.acordao_tjdft VALUES
('9000001', '00000001-1111-2222-3333-444444444441', '2026-03-10', '2026-03-15', '0700001-11.2026.8.07.0001',
 '1ª TURMA CÍVEL', 'ANA CANTARINO', 198,
 'DIREITO DO CONSUMIDOR. Dano moral in re ipsa. Recurso não provido.',
 'RECURSO NÃO PROVIDO.', FALSE, TRUE, FALSE, '1789000000.0'),

('9000002', '00000002-1111-2222-3333-444444444442', '2026-03-11', '2026-03-16', '0700002-22.2026.8.07.0001',
 'CÂMARA CRIMINAL', 'DEMETRIUS GOMES CAVALCANTI', 417,
 'PENAL. Usucapião extraordinário não se confunde com posse precária.',
 'APELAÇÃO DESPROVIDA.', FALSE, FALSE, FALSE, '1789000000.0'),

('9000003', '00000003-1111-2222-3333-444444444443', '2026-03-12', '2026-03-17', '0700003-33.2026.8.07.0001',
 '2ª TURMA RECURSAL', 'ALFEU MACHADO', 460,
 'CIVIL. Falha na prestação de serviço. Dano moral configurado.',
 'RECURSO PARCIALMENTE PROVIDO.', TRUE, TRUE, FALSE, '1789000000.0'),

('9000004', '00000004-1111-2222-3333-444444444444', '2026-03-13', '2026-03-18', '0700004-44.2026.8.07.0001',
 'CÂMARA CRIMINAL', 'ANA CANTARINO', 417,
 'ESTUPRO DE VULNERAVEL. Vitima menor identificada nos autos. Dano moral fixado.',
 'CONDENACAO MANTIDA.', FALSE, TRUE, TRUE, '1789000000.0'),

('9000005', '00000005-1111-2222-3333-444444444445', '2026-03-14', '2026-03-19', '0700005-55.2026.8.07.0001',
 '1ª TURMA CÍVEL', 'ALFEU MACHADO', 198,
 'FAMILIA. Guarda de menor. Dados sensiveis das partes no acordao.',
 'ACORDO HOMOLOGADO.', FALSE, FALSE, TRUE, '1789000000.0'),

('9000006', '00000006-1111-2222-3333-444444444446', '2026-03-15', '2026-03-20', '0700006-66.2026.8.07.0001',
 '1ª TURMA CÍVEL', 'ANA CANTARINO', 198,
 'PROCESSUAL CIVIL. Prescricao intercorrente reconhecida de oficio.',
 'APELACAO PROVIDA.', FALSE, TRUE, NULL, '1789000000.0');

-- dlt keeps this table itself. The load record model reads it, so the fixture
-- carries the two loads the records above belong to.
CREATE TABLE raw._dlt_loads (
    load_id     TEXT,
    status      BIGINT,
    inserted_at TIMESTAMPTZ
);

INSERT INTO raw._dlt_loads VALUES
('1789000000.0', 0, '2026-03-16 02:00:00+00'),
('1789000001.0', 0, '2026-03-17 02:00:00+00');

CREATE TABLE raw.espelho_stj (
    id                  TEXT,
    "dataDecisao"       TEXT,
    "dataPublicacao"    TEXT,
    "numeroProcesso"    TEXT,
    "nomeOrgaoJulgador" TEXT,
    "ministroRelator"   TEXT,
    ementa              TEXT,
    decisao             TEXT,
    _dlt_load_id        TEXT
);

-- A ementa vazia não entra. O órgão aparece com e sem acento para o mesmo
-- colegiado, e a transformação tem de escolher a grafia acentuada.
INSERT INTO raw.espelho_stj VALUES
('8000001', '20260310', 'DJe DATA:15/03/2026 Pág. 122',
 '2106100', 'PRIMEIRA SEÇÃO', 'JOÃO OTÁVIO DE NORONHA',
 'RECURSO ESPECIAL. Alienação fiduciária. Penhora de direitos aquisitivos.',
 'RECURSO ESPECIAL DESPROVIDO.', '1789000000.0'),

('8000002', '20260311', 'DJe DATA:16/03/2026 Pág. 87',
 '2106101', 'PRIMEIRA SECAO', 'NANCY ANDRIGHI',
 'PROCESSUAL CIVIL. Prescrição intercorrente em execução fiscal.',
 'RECURSO PROVIDO.', '1789000000.0'),

('8000003', '20260312', 'DJe DATA:17/03/2026 Pág. 45',
 '2106102', 'QUINTA TURMA', 'ANTONIO SALDANHA PALHEIRO',
 'PENAL. Dano moral coletivo. Dever de reparação reconhecido.',
 'AGRAVO REGIMENTAL NÃO PROVIDO.', '1789000000.0'),

('8000004', '20260313', 'DJe DATA:18/03/2026 Pág. 12',
 '2106103', 'QUINTA TURMA', 'ANTONIO SALDANHA PALHEIRO',
 '', 'DECISAO SEM EMENTA PUBLICADA.', '1789000000.0');
