-- =============================================================================
-- 10_bronze_ingest.sql  (job diário, modo source_mode = federation)
-- Copia as views do Synapse (via Lakehouse Federation) para tabelas Delta bronze.
-- Equivalente aos passos "Source = Sql.Database(...)" do Power Query.
--
-- Parâmetros substituídos pelo notebook src/run_sql.py:
--   ${catalog}         catálogo do projeto            (ex.: crm_reporting_prd)
--   ${source_catalog}  foreign catalog do Synapse     (ex.: synapse_crm_prd)
--   (os Leads são ingeridos à parte em 12_bronze_leads.sql - versões DEV e PRD)
-- =============================================================================

-- Pipeline (Leads + Deals) -> tabela "Pipeline" do PBI
CREATE OR REPLACE TABLE ${catalog}.bronze.crm_deal_pipeline AS
SELECT *, current_timestamp() AS _ingested_at
FROM ${source_catalog}.rpt.vw_CRMReportDealPipeline;

-- Orçamento (Investment Allocation)
CREATE OR REPLACE TABLE ${catalog}.bronze.investment_allocation AS
SELECT *, current_timestamp() AS _ingested_at
FROM ${source_catalog}.rpt.vw_InvestmentAllocation;

-- Utilização do CRM por plataforma/mês (User Access Platform)
CREATE OR REPLACE TABLE ${catalog}.bronze.crm_user_access_platform AS
SELECT *, current_timestamp() AS _ingested_at
FROM ${source_catalog}.rpt.vw_CRMUserAccess;
