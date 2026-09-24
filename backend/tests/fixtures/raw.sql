DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

CREATE TABLE raw.acordao_tjdft (
    identificador            TEXT,
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
('9000001', '2026-03-10', '2026-03-15', '0700001-11.2026.8.07.0001',
 '1ª TURMA CÍVEL', 'ANA CANTARINO', 198,
 'DIREITO DO CONSUMIDOR. Dano moral in re ipsa. Recurso não provido.',
 'RECURSO NÃO PROVIDO.', FALSE, TRUE, FALSE, '1789000000.0'),

('9000002', '2026-03-11', '2026-03-16', '0700002-22.2026.8.07.0001',
 'CÂMARA CRIMINAL', 'DEMETRIUS GOMES CAVALCANTI', 417,
 'PENAL. Usucapião extraordinário não se confunde com posse precária.',
 'APELAÇÃO DESPROVIDA.', FALSE, FALSE, FALSE, '1789000000.0'),

('9000003', '2026-03-12', '2026-03-17', '0700003-33.2026.8.07.0001',
 '2ª TURMA RECURSAL', 'ALFEU MACHADO', 460,
 'CIVIL. Falha na prestação de serviço. Dano moral configurado.',
 'RECURSO PARCIALMENTE PROVIDO.', TRUE, TRUE, FALSE, '1789000000.0'),

('9000004', '2026-03-13', '2026-03-18', '0700004-44.2026.8.07.0001',
 'CÂMARA CRIMINAL', 'ANA CANTARINO', 417,
 'ESTUPRO DE VULNERAVEL. Vitima menor identificada nos autos. Dano moral fixado.',
 'CONDENACAO MANTIDA.', FALSE, TRUE, TRUE, '1789000000.0'),

('9000005', '2026-03-14', '2026-03-19', '0700005-55.2026.8.07.0001',
 '1ª TURMA CÍVEL', 'ALFEU MACHADO', 198,
 'FAMILIA. Guarda de menor. Dados sensiveis das partes no acordao.',
 'ACORDO HOMOLOGADO.', FALSE, FALSE, TRUE, '1789000000.0'),

('9000006', '2026-03-15', '2026-03-20', '0700006-66.2026.8.07.0001',
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
