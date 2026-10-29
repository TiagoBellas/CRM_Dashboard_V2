-- =============================================================================
-- 40_grants.sql   (executar MANUALMENTE por um admin, após o 1º run do job)
-- Princípio: utilizadores finais só leem VIEWS gold seguras. Nunca silver/bronze.
-- Substitua:
--   ${catalog}            -> catálogo do ambiente
--   <app-sp-application-id> -> Application ID do service principal da app
--                            (Compute > Apps > a sua app > separador "Authorization")
--   <job-sp-application-id> -> service principal que executa o job (ou o seu utilizador)
-- =============================================================================

-- 1) Equipa de dados: gestão total do catálogo
GRANT ALL PRIVILEGES ON CATALOG ${catalog} TO `crm_report_admins`;

-- 2) Job (escreve bronze/silver/gold/ref)
GRANT USE CATALOG ON CATALOG ${catalog} TO `<job-sp-application-id>`;
GRANT USE SCHEMA, CREATE TABLE, CREATE VIEW, SELECT, MODIFY ON SCHEMA ${catalog}.bronze TO `<job-sp-application-id>`;
GRANT USE SCHEMA, CREATE TABLE, CREATE VIEW, SELECT, MODIFY ON SCHEMA ${catalog}.silver TO `<job-sp-application-id>`;
GRANT USE SCHEMA, CREATE TABLE, CREATE VIEW, SELECT, MODIFY ON SCHEMA ${catalog}.gold   TO `<job-sp-application-id>`;
GRANT USE SCHEMA, CREATE TABLE, CREATE VIEW, SELECT, MODIFY, READ VOLUME ON SCHEMA ${catalog}.ref TO `<job-sp-application-id>`;

-- 3) Utilizadores finais (modo recomendado: user authorization / OBO)
--    Precisam apenas de ler as views SEGURAS do schema gold.
GRANT USE CATALOG ON CATALOG ${catalog}           TO `crm_report_users`;
GRANT USE SCHEMA  ON SCHEMA  ${catalog}.gold      TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_pipeline                 TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_pipeline_dq              TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_leads                    TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_investment_allocation    TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_crm_user_access_platform TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_crm_users                TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_last_refresh             TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_my_access                TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_dim_stage                TO `crm_report_users`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_dim_segment              TO `crm_report_users`;
-- NÃO conceder: vw_pipeline_all, vw_rls_user_access_all, vw_pipeline_user_access_all,
--               vw_access_reconciliation (apenas admins).

-- 4) Service principal da app
--    Em modo OBO o SP só precisa de ler a data de refresh (opcional).
--    Em modo "app authorization" (fallback, AUTH_MODE=sp) precisa das views sem RLS,
--    porque a app aplica a regra com o e-mail do utilizador:
GRANT USE CATALOG ON CATALOG ${catalog}      TO `<app-sp-application-id>`;
GRANT USE SCHEMA  ON SCHEMA  ${catalog}.gold TO `<app-sp-application-id>`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_last_refresh             TO `<app-sp-application-id>`;
-- Só se AUTH_MODE=sp:
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_pipeline_all             TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_rls_user_access_all      TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_pipeline_user_access_all TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_investment_allocation    TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_crm_user_access_platform TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_crm_users                TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_leads_all                TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_leads_user_access_all    TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_dim_stage                TO `<app-sp-application-id>`;
-- GRANT SELECT ON VIEW ${catalog}.gold.vw_dim_segment              TO `<app-sp-application-id>`;

-- 5) Admins da app: ver reconciliação de acessos e dados completos
GRANT SELECT ON VIEW ${catalog}.gold.vw_access_reconciliation TO `crm_report_admins`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_pipeline_all          TO `crm_report_admins`;
GRANT SELECT ON VIEW ${catalog}.gold.vw_leads_source_comparison TO `crm_report_admins`;
