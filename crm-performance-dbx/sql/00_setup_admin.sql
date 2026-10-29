-- =============================================================================
-- 00_setup_admin.sql
-- EXECUTAR UMA ÚNICA VEZ, MANUALMENTE, por um administrador (Metastore/Workspace admin)
-- no SQL Editor do Databricks. NÃO faz parte do job diário.
--
-- Substitua ${catalog} pelo nome do catálogo do ambiente (ex.: crm_reporting_dev
-- ou crm_reporting_prd) antes de executar.
-- =============================================================================

-- 1) Catálogo do projeto.
--    Se o metastore NÃO tiver "root storage" definido, é obrigatório indicar a
--    localização gerida (MANAGED LOCATION) numa External Location já criada, ex.:
--    CREATE CATALOG IF NOT EXISTS ${catalog}
--      MANAGED LOCATION 'abfss://unity@<storageaccount>.dfs.core.windows.net/crm_reporting';
CREATE CATALOG IF NOT EXISTS ${catalog}
  COMMENT 'CRM Performance Reporting (migracao do Power BI CRM_Performance_Reporting_MVP_v1)';

-- 2) Schemas (arquitetura medalhão)
CREATE SCHEMA IF NOT EXISTS ${catalog}.bronze COMMENT 'Copia fiel das fontes (Synapse / ficheiros). Sem regras de negocio.';
CREATE SCHEMA IF NOT EXISTS ${catalog}.silver COMMENT 'Dados limpos + colunas calculadas do modelo Power BI (deterministicas).';
CREATE SCHEMA IF NOT EXISTS ${catalog}.gold   COMMENT 'Views consumidas pela Databricks App (RLS + colunas dependentes da data atual).';
CREATE SCHEMA IF NOT EXISTS ${catalog}.ref    COMMENT 'Dados de referencia / configuracao (stages, segmentos, lista de acessos RLS).';

-- 3) Volume para ficheiros carregados manualmente (lista RLS, dados de exemplo)
CREATE VOLUME IF NOT EXISTS ${catalog}.ref.landing
  COMMENT 'Ficheiros carregados manualmente: rls/UserPlatformCountry.xlsx, sample/*.csv';

-- 4) Grupos (criar antes na Account Console > User management > Groups):
--      crm_report_admins   -> equipa de dados (vê tudo, gere o projeto)
--      crm_report_users    -> todos os utilizadores do relatório
--    As permissões são atribuídas em 40_grants.sql.
