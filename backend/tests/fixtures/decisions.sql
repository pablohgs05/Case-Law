INSERT INTO core.decisao (
    fonte_codigo, identificador_fonte, tribunal_sigla, processo,
    orgao_julgador, relator, classe_cnj, data_julgamento, data_publicacao,
    data_referencia, ementa, tipo_texto, decisao_texto,
    turma_recursal, possui_inteiro_teor, url_fonte, link_valido, ementa_busca
)
VALUES
(
    'tjdft-jurisdf', '1000001', 'TJDFT', '0700001-11.2026.8.07.0001',
    '1ª TURMA CÍVEL', 'ANA CANTARINO', 198, '2026-03-10', '2026-03-15',
    '2026-03-10',
    'DIREITO DO CONSUMIDOR. Inscrição indevida em cadastro de inadimplentes. '
    'Dano moral in re ipsa. Ação procedente. Recurso não provido.',
    'ementa_completa', 'RECURSO NÃO PROVIDO. UNÂNIME.',
    FALSE, TRUE, 'https://jurisdf.tjdft.jus.br/detalhes/1000001', TRUE,
    TO_TSVECTOR('portugues_sem_acento',
        'DIREITO DO CONSUMIDOR. Inscrição indevida em cadastro de inadimplentes. '
        'Dano moral in re ipsa. Ação procedente. Recurso não provido.')
),
(
    'tjdft-jurisdf', '1000002', 'TJDFT', '0700002-22.2026.8.07.0001',
    'CÂMARA CRIMINAL', 'DEMETRIUS GOMES CAVALCANTI', 417, '2026-04-20', '2026-04-25',
    '2026-04-20',
    'PENAL. Usucapião extraordinário não se confunde com posse precária. '
    'Sentença mantida por seus próprios fundamentos.',
    'ementa_completa', 'APELAÇÃO CONHECIDA E DESPROVIDA.',
    FALSE, FALSE, 'https://jurisdf.tjdft.jus.br/detalhes/1000002', FALSE,
    TO_TSVECTOR('portugues_sem_acento',
        'PENAL. Usucapião extraordinário não se confunde com posse precária. '
        'Sentença mantida por seus próprios fundamentos.')
),
(
    'tjdft-jurisdf', '1000003', 'TJDFT', '0700003-33.2026.8.07.0001',
    '2ª TURMA RECURSAL', 'ALFEU MACHADO', 460, '2026-05-05', '2026-05-09',
    '2026-05-05',
    'CIVIL. Responsabilidade civil por falha na prestação de serviço. '
    'Dano moral configurado. Danos materiais afastados.',
    'ementa_completa', 'RECURSO PARCIALMENTE PROVIDO.',
    TRUE, TRUE, 'https://jurisdf.tjdft.jus.br/detalhes/1000003', NULL,
    TO_TSVECTOR('portugues_sem_acento',
        'CIVIL. Responsabilidade civil por falha na prestação de serviço. '
        'Dano moral configurado. Danos materiais afastados.')
),
(
    'tjdft-jurisdf', '1000004', 'TJDFT', '0700004-44.2026.8.07.0001',
    '3ª TURMA CÍVEL', 'JOÃO EGMONT', 1116, '2026-06-11', '2026-06-18',
    '2026-06-11',
    'PROCESSUAL CIVIL E TRIBUTÁRIO. EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE. I. CASO EM EXAME 1. Apelação interposta contra sentença que julgou extinta a execução fiscal, ao reconhecer a prescrição intercorrente após longo período de suspensão do feito sem localização de bens penhoráveis do devedor. II. QUESTÃO EM DISCUSSÃO 2. A controvérsia consiste em definir se o termo inicial da suspensão se conta da ciência da primeira diligência infrutífera ou do despacho que a determinou. III. RAZÕES DE DECIDIR 3. A prescrição intercorrente rege-se pelo artigo 40 da Lei de Execuções Fiscais, cujo prazo corre automaticamente da ciência da primeira tentativa frustrada. 4. O mero peticionamento nos autos não interrompe o prazo, conforme entendimento consolidado. IV. DISPOSITIVO 5. Apelação conhecida e desprovida, mantida a sentença por seus próprios fundamentos.',
    'ementa_completa', 'APELAÇÃO CONHECIDA E DESPROVIDA.',
    FALSE, TRUE, 'https://jurisdf.tjdft.jus.br/detalhes/1000004', TRUE,
    TO_TSVECTOR('portugues_sem_acento',
        'PROCESSUAL CIVIL E TRIBUTÁRIO. EXECUÇÃO FISCAL. PRESCRIÇÃO INTERCORRENTE. I. CASO EM EXAME 1. Apelação interposta contra sentença que julgou extinta a execução fiscal, ao reconhecer a prescrição intercorrente após longo período de suspensão do feito sem localização de bens penhoráveis do devedor. II. QUESTÃO EM DISCUSSÃO 2. A controvérsia consiste em definir se o termo inicial da suspensão se conta da ciência da primeira diligência infrutífera ou do despacho que a determinou. III. RAZÕES DE DECIDIR 3. A prescrição intercorrente rege-se pelo artigo 40 da Lei de Execuções Fiscais, cujo prazo corre automaticamente da ciência da primeira tentativa frustrada. 4. O mero peticionamento nos autos não interrompe o prazo, conforme entendimento consolidado. IV. DISPOSITIVO 5. Apelação conhecida e desprovida, mantida a sentença por seus próprios fundamentos.')
);
