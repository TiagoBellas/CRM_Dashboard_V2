-- =============================================================================
-- 30_gold_views.sql  (job diário - recriar views é instantâneo)
-- Views consumidas pela Databricks App.
--   * vw_pipeline_all : silver.pipeline + colunas DAX que dependem de TODAY()
--                       SEM segurança -> só admins e o service principal da app
--   * vw_pipeline     : view SEGURA (RLS dinâmico por current_user()) + filtro de
--                       relatório "Show Row - Closed This Year Or Blank = 1"
--   * restantes views de apoio (orçamento, utilização, utilizadores, DQ, acessos)
-- Parâmetro ${admin_group}: grupo que vê todos os dados (ex.: crm_report_admins).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Pipeline com colunas dependentes da data atual
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline_all
COMMENT 'Pipeline completo (sem RLS) com colunas dependentes de TODAY(). Acesso restrito.'
AS
WITH t AS (
  SELECT
    p.*,
    CAST(current_date() AS TIMESTAMP) AS _as_of_ts,
    -- "Terminal inline" de [Stage Age Days (Snapshot)]
    CASE
      WHEN upper(p.n_active) = 'LEAD' AND upper(coalesce(p.n_lead_status, '')) = 'REJECTED' THEN 'Lost'
      WHEN upper(p.n_active) = 'LOST'                                                     THEN 'Lost'
      WHEN upper(p.n_active) IN ('WON', 'CLOSED')                                          THEN 'Won'
      ELSE 'Active'
    END AS _age_terminal,
    -- "Stage inline" de [Stage Age Days (Snapshot)]
    CASE
      WHEN upper(p.n_active) = 'LEAD' AND upper(coalesce(p.n_lead_status, '')) = 'REJECTED' THEN 'Lead'
      WHEN upper(p.n_active) = 'LOST'   THEN coalesce(p.n_last, 'Early Prospect')
      WHEN upper(p.n_active) = 'CLOSED' THEN 'Won'
      WHEN p.n_active IS NULL           THEN 'Lead'
      ELSE p.n_active
    END AS _age_stage
  FROM ${catalog}.silver.pipeline p
),
t2 AS (
  SELECT
    t.*,
    CASE upper(_age_stage)
      WHEN 'LEAD'                   THEN created_on
      WHEN 'EARLY PROSPECT'         THEN created_on
      WHEN 'NBO / PRELIMINARY BIDS' THEN passed_to_nbo
      WHEN 'IN DUE DILIGENCE'       THEN passed_to_dd
      WHEN 'IC APPROVED'            THEN passed_to_ic
      WHEN 'WON, CLOSING'           THEN passed_to_won
    END AS _age_start,
    CASE
      WHEN _age_terminal = 'Lost' THEN coalesce(closed_on, modified_on, _as_of_ts)
      ELSE CASE upper(_age_stage)
             WHEN 'LEAD'                   THEN coalesce(closed_on,     _as_of_ts)
             WHEN 'EARLY PROSPECT'         THEN coalesce(passed_to_nbo, _as_of_ts)
             WHEN 'NBO / PRELIMINARY BIDS' THEN coalesce(passed_to_dd,  _as_of_ts)
             WHEN 'IN DUE DILIGENCE'       THEN coalesce(passed_to_ic,  _as_of_ts)
             WHEN 'IC APPROVED'            THEN coalesce(passed_to_won, _as_of_ts)
             WHEN 'WON, CLOSING'           THEN coalesce(closed_on,     _as_of_ts)
           END
    END AS _age_end
  FROM t
),
t3 AS (
  SELECT
    t2.*,
    -- [Stage Age Days (Snapshot)]
    CASE
      WHEN _age_terminal = 'Won' THEN NULL
      WHEN _age_start IS NOT NULL AND _age_end IS NOT NULL AND _age_end >= _age_start
        THEN datediff(CAST(_age_end AS DATE), CAST(_age_start AS DATE))
    END AS stage_age_days_snapshot,
    -- [Average Deal Age Column]
    datediff(CAST(coalesce(closed_on, _as_of_ts) AS DATE), CAST(created_on AS DATE)) AS average_deal_age_days,
    -- [Show Row - Closed This Year Or Blank]  (filtro ao nível do relatório no PBI)
    CASE WHEN closed_on IS NULL OR year(closed_on) = year(current_date()) THEN 1 ELSE 0 END AS show_row_closed_this_year_or_blank
  FROM t2
)
SELECT
  t3.*,
  -- [Time in Stage]
  CASE
    WHEN terminal_snapshot = 'Won'            THEN 'N/A'
    WHEN stage_age_days_snapshot IS NULL      THEN 'Unknown'
    WHEN stage_age_days_snapshot >= 90 AND stage_age_days_snapshot < 180 THEN 'More than 90 days'
    WHEN stage_age_days_snapshot >= 180       THEN 'More than 180 days'
    ELSE 'Less than 90 days'
  END AS time_in_stage
FROM t3;

-- ---------------------------------------------------------------------------
-- VIEW SEGURA (substitui a role RLS_Dynamic do Power BI)
-- current_user() devolve o e-mail do utilizador que está a consultar. Com a
-- Databricks App em modo "user authorization" (OBO), é o utilizador final.
-- @dbx-only-begin
CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline
COMMENT 'Pipeline com RLS dinamico (equivalente a role RLS_Dynamic) e filtro de relatorio.'
AS
SELECT p.*
FROM ${catalog}.gold.vw_pipeline_all p
WHERE p.show_row_closed_this_year_or_blank = 1
  AND (
        is_account_group_member('${admin_group}')
     OR EXISTS (SELECT 1 FROM ${catalog}.silver.rls_user_access a
                WHERE a.rls_email = lower(current_user()) AND a.rls_access_type = 'GLOBAL')
     OR EXISTS (SELECT 1 FROM ${catalog}.silver.pipeline_user_access x
                WHERE x.rls_email = lower(current_user()) AND x.record_id = p.record_id)
  );
-- @dbx-only-end
-- @duckdb-only-begin
--duckdb: CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline AS
--duckdb: SELECT p.* FROM ${catalog}.gold.vw_pipeline_all p WHERE p.show_row_closed_this_year_or_blank = 1;
-- @duckdb-only-end

-- Mesma regra mas para TODAS as linhas (sem o filtro de relatório) -> página DQ
-- @dbx-only-begin
CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline_dq
COMMENT 'Pipeline com RLS, sem filtro de relatorio, para a pagina de qualidade de dados.'
AS
SELECT p.*
FROM ${catalog}.gold.vw_pipeline_all p
WHERE is_account_group_member('${admin_group}')
   OR EXISTS (SELECT 1 FROM ${catalog}.silver.rls_user_access a
              WHERE a.rls_email = lower(current_user()) AND a.rls_access_type = 'GLOBAL')
   OR EXISTS (SELECT 1 FROM ${catalog}.silver.pipeline_user_access x
              WHERE x.rls_email = lower(current_user()) AND x.record_id = p.record_id);
-- @dbx-only-end
-- @duckdb-only-begin
--duckdb: CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline_dq AS SELECT p.* FROM ${catalog}.gold.vw_pipeline_all p;
-- @duckdb-only-end

-- Views auxiliares para o modo "app authorization" (service principal):
-- a app aplica a MESMA regra passando o e-mail do utilizador como parâmetro.
CREATE OR REPLACE VIEW ${catalog}.gold.vw_rls_user_access_all AS
SELECT rls_email, rls_access_type, rls_match_platform, rls_country_token, platform, country, full_name
FROM ${catalog}.silver.rls_user_access;

CREATE OR REPLACE VIEW ${catalog}.gold.vw_pipeline_user_access_all AS
SELECT rls_email, record_id FROM ${catalog}.silver.pipeline_user_access;

-- Os acessos do próprio utilizador (o PBI aplicava RLS também à tabela RLS)
-- @dbx-only-begin
CREATE OR REPLACE VIEW ${catalog}.gold.vw_my_access AS
SELECT rls_email, rls_access_type, platform, country
FROM ${catalog}.silver.rls_user_access
WHERE rls_email = lower(current_user());
-- @dbx-only-end

-- ---------------------------------------------------------------------------
-- Leads: versão ATIVA (ref.app_config.leads_source_active) com RLS
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW ${catalog}.gold.vw_leads_all AS
SELECT l.*,
       CASE WHEN l.source_env = (SELECT config_value FROM ${catalog}.ref.app_config
                                 WHERE config_key = 'leads_source_active') THEN 1 ELSE 0 END AS is_active_source
FROM ${catalog}.silver.leads l;

-- @dbx-only-begin
CREATE OR REPLACE VIEW ${catalog}.gold.vw_leads
COMMENT 'Leads da origem ativa (DEV ou PRD) com RLS dinamico.'
AS
SELECT l.*
FROM ${catalog}.gold.vw_leads_all l
WHERE l.is_active_source = 1
  AND (   is_account_group_member('${admin_group}')
       OR EXISTS (SELECT 1 FROM ${catalog}.silver.rls_user_access a
                  WHERE a.rls_email = lower(current_user()) AND a.rls_access_type = 'GLOBAL')
       OR EXISTS (SELECT 1 FROM ${catalog}.silver.leads_user_access x
                  WHERE x.rls_email = lower(current_user())
                    AND x.source_env = l.source_env AND x.record_id = l.record_id));
-- @dbx-only-end
-- @duckdb-only-begin
--duckdb: CREATE OR REPLACE VIEW ${catalog}.gold.vw_leads AS SELECT * FROM ${catalog}.gold.vw_leads_all WHERE is_active_source = 1;
-- @duckdb-only-end

CREATE OR REPLACE VIEW ${catalog}.gold.vw_leads_user_access_all AS
SELECT rls_email, source_env, record_id FROM ${catalog}.silver.leads_user_access;

-- Comparação DEV x PRD (apenas admins) - apoia a decisão de negócio (A1)
CREATE OR REPLACE VIEW ${catalog}.gold.vw_leads_source_comparison AS
SELECT
  l.source_env,
  max(l.is_active_source)                                     AS is_active_source,
  COUNT(*)                                                    AS leads,
  COUNT(DISTINCT l.lead_id)                                   AS distinct_lead_ids,
  SUM(CASE WHEN p.lead_id IS NOT NULL THEN 1 ELSE 0 END)      AS leads_matching_pipeline,
  SUM(CASE WHEN p.lead_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*) AS pct_matching_pipeline,
  SUM(CASE WHEN upper(l.lead_status) = 'APPROVED' AND l.closed_on IS NOT NULL THEN 1 ELSE 0 END) AS approved_closed_leads,
  avg(CASE WHEN upper(l.lead_status) = 'APPROVED' AND l.closed_on IS NOT NULL
           THEN datediff(CAST(l.closed_on AS DATE), CAST(l.created_on AS DATE)) END) AS avg_days_in_lead_stage,
  min(l.created_on) AS min_created_on,
  max(l.created_on) AS max_created_on
FROM ${catalog}.gold.vw_leads_all l
LEFT JOIN (SELECT DISTINCT lead_id FROM ${catalog}.silver.pipeline WHERE lead_id IS NOT NULL) p
  ON p.lead_id = l.lead_id
GROUP BY l.source_env;

-- ---------------------------------------------------------------------------
-- Orçamento, utilização do CRM, utilizadores
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW ${catalog}.gold.vw_investment_allocation AS
SELECT investment_allocation_id, platform, country_name, year, budget_base, platform_id
FROM ${catalog}.silver.investment_allocation;

CREATE OR REPLACE VIEW ${catalog}.gold.vw_crm_user_access_platform AS
SELECT u.*
FROM ${catalog}.silver.crm_user_access_platform u
WHERE u.platform NOT IN (SELECT platform FROM ${catalog}.ref.usage_excluded_platforms);

CREATE OR REPLACE VIEW ${catalog}.gold.vw_crm_users AS
SELECT
  user_id, user_name, title, business_unit, last_login, logins_done,
  CASE
    WHEN last_login IS NULL                                  THEN 'No access recorded'
    WHEN datediff(current_date(), last_login) <= 30          THEN 'In the last 30 days'
    WHEN datediff(current_date(), last_login) <= 60          THEN 'In the last 60 days'
    WHEN datediff(current_date(), last_login) <= 90          THEN 'In the last 90 days'
    ELSE 'More than 90 days'
  END AS last_login_range
FROM ${catalog}.silver.crm_users
WHERE business_unit NOT IN ('Development', 'Service Account');

-- ---------------------------------------------------------------------------
-- Metadados
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW ${catalog}.gold.vw_last_refresh AS
SELECT max(_processed_at) AS last_refresh_ts FROM ${catalog}.silver.pipeline;

CREATE OR REPLACE VIEW ${catalog}.gold.vw_access_reconciliation AS
SELECT * FROM ${catalog}.silver.sec_access_reconciliation;

CREATE OR REPLACE VIEW ${catalog}.gold.vw_dim_stage   AS SELECT * FROM ${catalog}.ref.dim_stage;
CREATE OR REPLACE VIEW ${catalog}.gold.vw_dim_segment AS SELECT * FROM ${catalog}.ref.dim_segment;
