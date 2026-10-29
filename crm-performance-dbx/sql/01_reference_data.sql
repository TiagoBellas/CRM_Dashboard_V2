-- =============================================================================
-- 01_reference_data.sql  (executado pelo job; idempotente)
-- Recria as tabelas de referência que no Power BI eram tabelas calculadas DAX
-- (_DimStage, _DimSegment) e listas "hard-coded" no Power Query / DAX.
-- =============================================================================

-- _DimStage  (DATATABLE no PBI + colunas calculadas Stage (Display) / Stage Group)
CREATE OR REPLACE TABLE ${catalog}.ref.dim_stage AS
SELECT
  stage_index,
  stage_name,
  concat(CAST(stage_index AS STRING), '. ', stage_name) AS stage_display,
  'Pipeline Stage'                                        AS stage_group
FROM (VALUES
  (0, 'Lost'),
  (1, 'Lead'),
  (2, 'Early Prospect'),
  (3, 'NBO / Preliminary Bids'),
  (4, 'In Due Diligence'),
  (5, 'IC Approved'),
  (6, 'Won, Closing'),
  (7, 'Won')
) AS t(stage_index, stage_name);

-- _DimSegment
CREATE OR REPLACE TABLE ${catalog}.ref.dim_segment AS
SELECT * FROM (VALUES
  ('Real Estate Lending',             'RE Lending',         1),
  ('Opportunistic Credit',            'Opp. Credit',        2),
  ('Non-Performing',                  'NPL',                3),
  ('Bankruptcies and restructuring',  'B&R',                4),
  ('Single Name Credits',             'SN Credit',          5),
  ('Secured Collaterals & Value-add', 'Secured Coll. & VA', 6),
  ('Real-estate Equity',              'RE Equity',          7),
  ('Investment Grade Asset-Backed',   'IG Asset-Backed',    8),
  ('Other',                           'Other',              9)
) AS t(segment_name, segment_reduced, segment_index);

-- Mapeamento de segmentos (substitui a lista do passo "Mapped Unknown Segments to Other"
-- do Power Query). Valores que NÃO estejam nesta tabela passam a 'Other'.
-- ATENÇÃO (ver docs/00_Analise_PowerBI.md, achado A4): a lista original tinha erros
-- ortográficos ('Oportunistic Credit', 'Investment Grande Asset-Backed',
-- 'Real State Lending'). Aqui os erros são mapeados para o nome correto e os nomes
-- corretos também são aceites. Validar com o negócio.
CREATE OR REPLACE TABLE ${catalog}.ref.segment_mapping AS
SELECT * FROM (VALUES
  ('Real Estate Lending',              'Real Estate Lending',             'original'),
  ('Real State Lending',               'Real Estate Lending',             'original - erro ortografico corrigido'),
  ('Bankruptcies and restructuring',   'Bankruptcies and restructuring',  'original'),
  ('Investment Grande Asset-Backed',   'Investment Grade Asset-Backed',   'original - erro ortografico corrigido'),
  ('Investment Grade Asset-Backed',    'Investment Grade Asset-Backed',   'adicionado na migracao'),
  ('Non-Performing',                   'Non-Performing',                  'original'),
  ('Oportunistic Credit',              'Opportunistic Credit',            'original - erro ortografico corrigido'),
  ('Opportunistic Credit',             'Opportunistic Credit',            'adicionado na migracao'),
  ('Other',                            'Other',                           'original'),
  ('Real-estate Equity',               'Real-estate Equity',              'original'),
  ('Secured Collaterals & Value-add',  'Secured Collaterals & Value-add', 'original'),
  ('Single Name Credits',              'Single Name Credits',             'original')
) AS t(source_value, segment_name, note);

-- Alias de plataformas usados na regra RLS (colunas DAX "RLS Match Platform")
CREATE OR REPLACE TABLE ${catalog}.ref.platform_rls_alias AS
SELECT * FROM (VALUES
  ('EAGLE STREET PARTNERS', 'EAGLE STREET'),
  ('EAGLE STREET',          'EAGLE STREET'),
  ('MAVEN',                 'MAVEN REAL ESTATE'),
  ('MAVEN REAL ESTATE',     'MAVEN REAL ESTATE')
) AS t(platform_upper, rls_platform);

-- Configuração (medida DAX [Base URL] e formid usado no URL do registo no CRM)
CREATE OR REPLACE TABLE ${catalog}.ref.app_config AS
SELECT * FROM (VALUES
  ('crm_base_url',     'https://arrowglobal.crm4.dynamics.com/main.aspx?appid=f9e6bb92-6cb5-4cae-8568-2483fa4061e3'),
  ('crm_deal_form_id', '6309cb6a-2cb2-4747-a239-c64b41def6a7'),
  -- Origem ATIVA dos Leads: 'DEV' (igual ao Power BI atual) ou 'PRD'.
  -- Vem do parâmetro do job "leads_source_active" (ver docs, achado A1).
  ('leads_source_active', '${leads_source_active}')
) AS t(config_key, config_value);

-- Plataformas excluídas da página "DMS Usage" (filtros de visual no PBI)
CREATE OR REPLACE TABLE ${catalog}.ref.usage_excluded_platforms AS
SELECT * FROM (VALUES
  ('Development'),
  ('Service Account'),
  ('Whitestar/Norfin Non-CRM Users')
) AS t(platform);
