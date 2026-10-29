-- =============================================================================
-- 02_federation_admin.sql
-- EXECUTAR UMA ÚNICA VEZ, MANUALMENTE (admin). Liga o Databricks ao Azure Synapse
-- Serverless SQL onde estão as views rpt.* usadas hoje pelo Power BI.
--
-- Pré-requisitos (ver docs/01_Guia_Implementacao.md, Fase 3):
--   a) Login SQL criado no Synapse Serverless com permissão de leitura na base
--      dataverse_arrowcrm_org375adb08 (pedido à equipa que gere o Synapse).
--   b) Secret scope "crm-reporting" com as chaves synapse-user / synapse-password.
--   c) Conectividade de rede do SQL Warehouse serverless até
--      dynamicsynapseprod-ondemand.sql.azuresynapse.net:1433
--      (firewall do Synapse / Network Connectivity Configuration do Databricks).
-- =============================================================================

-- 1) Ligação (Unity Catalog connection) ao Synapse
CREATE CONNECTION IF NOT EXISTS conn_synapse_crm_prd TYPE sqldw
OPTIONS (
  host     'dynamicsynapseprod-ondemand.sql.azuresynapse.net',
  port     '1433',
  user     secret('crm-reporting', 'synapse-user'),
  password secret('crm-reporting', 'synapse-password')
)
COMMENT 'Synapse Serverless (Dataverse Synapse Link) - CRM produção';

-- 2) Catálogo estrangeiro que espelha a base de dados do Dataverse
CREATE FOREIGN CATALOG IF NOT EXISTS synapse_crm_prd
USING CONNECTION conn_synapse_crm_prd
OPTIONS (database 'dataverse_arrowcrm_org375adb08')
COMMENT 'Foreign catalog: views rpt.* do CRM (produção)';

-- 2b) Ligação e catálogo para a base de DEV (origem atual dos Leads no PBI - achado A1)
--     Necessário enquanto o negócio não decidir entre DEV e PRD para os Leads.
CREATE CONNECTION IF NOT EXISTS conn_synapse_crm_dev TYPE sqldw
OPTIONS (
  host     'dynamicsynapse-ondemand.sql.azuresynapse.net',
  port     '1433',
  user     secret('crm-reporting', 'synapse-dev-user'),
  password secret('crm-reporting', 'synapse-dev-password')
)
COMMENT 'Synapse Serverless - CRM DEV (apenas Leads)';

CREATE FOREIGN CATALOG IF NOT EXISTS synapse_crm_dev
USING CONNECTION conn_synapse_crm_dev
OPTIONS (database 'dataverse_arrowcrmdev_unq1b6f845c7703ee11a66d000d3a64d')
COMMENT 'Foreign catalog: CRM DEV (rpt.vw_CRMLeads)';

-- 3) Teste rápido (deve devolver linhas)
SELECT COUNT(*) AS n FROM synapse_crm_prd.rpt.vw_CRMReportDealPipeline;
SELECT COUNT(*) AS n FROM synapse_crm_prd.rpt.vw_InvestmentAllocation;
SELECT COUNT(*) AS n FROM synapse_crm_prd.rpt.vw_CRMUserAccess;
SELECT COUNT(*) AS n FROM synapse_crm_prd.rpt.vw_CRMLeads;   -- Leads PRD
SELECT COUNT(*) AS n FROM synapse_crm_dev.rpt.vw_CRMLeads;   -- Leads DEV
-- Opcional (substitui a tabela User_Access que no PBI estava "colada" no modelo):
-- SELECT COUNT(*) FROM synapse_crm_prd.crm.vAllUsers;

-- 4) Permissões para a identidade que executa o job (service principal do job)
--    Substitua <job-sp-application-id> pelo Application ID do service principal.
GRANT USE CATALOG ON CATALOG synapse_crm_prd TO `<job-sp-application-id>`;
GRANT USE SCHEMA, SELECT ON CATALOG synapse_crm_prd TO `<job-sp-application-id>`;
GRANT USE CONNECTION ON CONNECTION conn_synapse_crm_prd TO `<job-sp-application-id>`;
GRANT USE CATALOG ON CATALOG synapse_crm_dev TO `<job-sp-application-id>`;
GRANT USE SCHEMA, SELECT ON CATALOG synapse_crm_dev TO `<job-sp-application-id>`;
GRANT USE CONNECTION ON CONNECTION conn_synapse_crm_dev TO `<job-sp-application-id>`;
