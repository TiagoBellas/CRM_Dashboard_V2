-- =============================================================================
-- 12_bronze_leads.sql  (job diário - executado UMA VEZ POR AMBIENTE DE ORIGEM)
-- Achado A1: no Power BI a tabela "Leads" vinha da base de DEV
--   (dynamicsynapse-ondemand / dataverse_arrowcrmdev_...), ao contrário das
--   restantes tabelas (PRD). Enquanto o negócio não decide, ingerimos AMBAS as
--   versões para a mesma tabela, identificadas pela coluna _source_env.
--   A versão usada pela app é escolhida em ref.app_config (leads_source_active).
--
-- Parâmetros:
--   ${leads_env}       'DEV' ou 'PRD'
--   ${leads_catalog}   foreign catalog correspondente (synapse_crm_dev / synapse_crm_prd)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ${catalog}.bronze.crm_leads (
  RecordType STRING, RecordId STRING, DealId STRING, LeadId STRING,
  SourceSystem STRING, EntityName STRING, Name STRING,
  CreatedOn TIMESTAMP, ModifiedOn TIMESTAMP, ClosedOn TIMESTAMP,
  StateName STRING, StatusName STRING, ActiveStage STRING, LeadStatus STRING,
  ClosureReason STRING, Segment STRING, Platform STRING, Template STRING,
  CentralMD STRING, FundName STRING, CountryName STRING, OriginatorName STRING,
  Seller STRING, OwnerName STRING, AmountBase DOUBLE, CurrencyName STRING,
  LastDealStatus STRING, ExchangeRate DOUBLE, AmountInEuro DOUBLE,
  PassedToNBO STRING, PassedToDD STRING, PassedToIC STRING, PassedToWon STRING,
  DescriptionText STRING,
  _source_env STRING, _ingested_at TIMESTAMP
);

DELETE FROM ${catalog}.bronze.crm_leads WHERE _source_env = '${leads_env}';

INSERT INTO ${catalog}.bronze.crm_leads
SELECT
  CAST(RecordType AS STRING), CAST(RecordId AS STRING), CAST(DealId AS STRING), CAST(LeadId AS STRING),
  CAST(SourceSystem AS STRING), CAST(EntityName AS STRING), CAST(Name AS STRING),
  CAST(CreatedOn AS TIMESTAMP), CAST(ModifiedOn AS TIMESTAMP), CAST(ClosedOn AS TIMESTAMP),
  CAST(StateName AS STRING), CAST(StatusName AS STRING), CAST(ActiveStage AS STRING), CAST(LeadStatus AS STRING),
  CAST(ClosureReason AS STRING), CAST(Segment AS STRING), CAST(Platform AS STRING), CAST(Template AS STRING),
  CAST(CentralMD AS STRING), CAST(FundName AS STRING), CAST(CountryName AS STRING), CAST(OriginatorName AS STRING),
  CAST(Seller AS STRING), CAST(OwnerName AS STRING), CAST(AmountBase AS DOUBLE), CAST(CurrencyName AS STRING),
  CAST(LastDealStatus AS STRING), CAST(ExchangeRate AS DOUBLE), CAST(AmountInEuro AS DOUBLE),
  CAST(PassedToNBO AS STRING), CAST(PassedToDD AS STRING), CAST(PassedToIC AS STRING), CAST(PassedToWon AS STRING),
  CAST(DescriptionText AS STRING),
  '${leads_env}', current_timestamp()
FROM ${leads_catalog}.rpt.vw_CRMLeads;
