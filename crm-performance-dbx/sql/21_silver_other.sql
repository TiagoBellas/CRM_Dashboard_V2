-- =============================================================================
-- 21_silver_other.sql  (job diário)
-- Restantes tabelas do modelo PBI + preparação da segurança (RLS).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Investment Allocation (orçamento "PP" por plataforma/país/ano)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ${catalog}.silver.investment_allocation AS
SELECT
  InvestmentAllocationId          AS investment_allocation_id,
  Platform                        AS platform,
  CountryName                     AS country_name,
  CAST(Year AS INT)               AS year,
  CAST(BudgetBase AS DOUBLE)      AS budget_base,
  PlatformId                      AS platform_id,
  current_timestamp()             AS _processed_at
FROM ${catalog}.bronze.investment_allocation;

-- ---------------------------------------------------------------------------
-- Leads  (tabela "Leads" do PBI) - contém as DUAS versões (DEV e PRD), ver A1.
-- Só é usada no tempo médio do stage "Lead" (medida Avg Days In Stage).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ${catalog}.silver.leads AS
SELECT
  _source_env AS source_env,
  RecordType AS record_type, RecordId AS record_id, DealId AS deal_id, LeadId AS lead_id,
  SourceSystem AS source_system, EntityName AS entity_name, Name AS record_name,
  CAST(CreatedOn AS TIMESTAMP) AS created_on, CAST(ModifiedOn AS TIMESTAMP) AS modified_on,
  CAST(ClosedOn AS TIMESTAMP)  AS closed_on,
  StateName AS state_name, StatusName AS status_name, ActiveStage AS active_stage,
  LeadStatus AS lead_status, ClosureReason AS closure_reason, Segment AS segment,
  Platform AS platform, Template AS vertical, CentralMD AS central_md, FundName AS fund_name,
  CountryName AS country_name, OriginatorName AS originator, Seller AS seller, OwnerName AS owner_name,
  CAST(AmountBase AS DOUBLE) AS amount_base, CurrencyName AS currency_name,
  CAST(ExchangeRate AS DOUBLE) AS exchange_rate,
  CAST(AmountInEuro AS DOUBLE) AS amount_eur,          -- "Amount (€)" no PBI
  CASE WHEN upper(trim(coalesce(Platform, ''))) = '' THEN NULL
       ELSE coalesce(pa.rls_platform, upper(trim(replace(coalesce(Platform, ''), chr(160), ' ')))) END AS rls_match_platform,
  nullif(upper(trim(replace(coalesce(CountryName, ''), chr(160), ' '))), '')                         AS rls_match_country,
  current_timestamp() AS _processed_at
FROM ${catalog}.bronze.crm_leads l
LEFT JOIN ${catalog}.ref.platform_rls_alias pa
  ON pa.platform_upper = upper(trim(replace(coalesce(l.Platform, ''), chr(160), ' ')));

-- ---------------------------------------------------------------------------
-- User Access Platform (utilização mensal do CRM) + colunas DAX Year/Month/MonthNumber
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ${catalog}.silver.crm_user_access_platform AS
SELECT
  SourceSystem                         AS source_system,
  EntityName                           AS entity_name,
  Platform                             AS platform,
  CAST(MonthStart AS DATE)             AS month_start,
  CAST(MonthKey AS INT)                AS month_key,
  CAST(LicensedUsers AS INT)           AS licensed_users,
  CAST(ActiveUsers AS INT)             AS active_users,
  CAST(AccessRecords AS INT)           AS access_records,
  CAST(LastAccessInMonthUtc AS TIMESTAMP) AS last_access_in_month_utc,
  CAST(LoginRatePct AS DOUBLE)         AS login_rate_pct,
  year(CAST(MonthStart AS DATE))       AS year,
  CASE month(CAST(MonthStart AS DATE))
       WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April'
       WHEN 5 THEN 'May' WHEN 6 THEN 'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August'
       WHEN 9 THEN 'September' WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December' END AS month_name,
  month(CAST(MonthStart AS DATE))      AS month_number,
  current_timestamp()                  AS _processed_at
FROM ${catalog}.bronze.crm_user_access_platform;

-- ---------------------------------------------------------------------------
-- Utilizadores do CRM (tabela "User_Access" do PBI, agora atualizada da fonte)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ${catalog}.silver.crm_users AS
SELECT
  CAST(UserID AS STRING)                              AS user_id,
  UserName                                            AS user_name,
  CASE WHEN Title IS NULL OR Title = 'NULL' THEN '-' ELSE Title END AS title,   -- #"Replaced value"
  BusinessUnit                                        AS business_unit,
  try_cast(LastLogin AS DATE)                         AS last_login,     -- a fonte tem "-" para "sem login"
  try_cast(LoginsDone AS INT)                         AS logins_done,
  current_timestamp()                                 AS _processed_at
FROM ${catalog}.bronze.crm_all_users
WHERE coalesce(ActiveCRMUser, 'Yes') = 'Yes';

-- ---------------------------------------------------------------------------
-- RLS: lista de acessos (equivalente a RLS_UserAccess_Raw + colunas DAX)
-- A tabela ref.rls_user_access_raw é carregada pelo notebook
-- src/load_files_from_volume.py a partir do Excel/CSV no volume ref.landing
-- (já com o país "explodido": 1 linha por utilizador x país, como no PQ).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE ${catalog}.silver.rls_user_access AS
WITH r AS (
  SELECT
    user_id,
    full_name,
    platform,
    country,
    primary_email,
    nullif(lower(trim(replace(coalesce(primary_email, ''), chr(160), ' '))), '') AS rls_email,
    upper(trim(replace(coalesce(platform, ''), chr(160), ' ')))                  AS platform_upper,
    upper(trim(replace(coalesce(country, ''), chr(160), ' ')))                   AS country_upper
  FROM ${catalog}.ref.rls_user_access_raw
),
r2 AS (
  SELECT
    r.*,
    CASE WHEN r.platform_upper = '' THEN NULL ELSE coalesce(pa.rls_platform, r.platform_upper) END AS rls_match_platform,
    CASE WHEN r.country_upper = '' THEN NULL
         ELSE concat('|', replace(replace(replace(replace(r.country_upper, ' / ', '/'), '/ ', '/'), ' /', '/'), '/', '|'), '|')
    END AS rls_country_token
  FROM r
  LEFT JOIN ${catalog}.ref.platform_rls_alias pa ON pa.platform_upper = r.platform_upper
)
SELECT
  r2.user_id, r2.full_name, r2.platform, r2.country, r2.primary_email, r2.rls_email,
  r2.rls_match_platform, r2.rls_country_token,
  CASE
    WHEN rls_match_platform = 'CENTRAL'      AND instr(coalesce(rls_country_token, ''), '|ALL|') > 0      THEN 'GLOBAL'
    WHEN rls_match_platform = 'ALL PORTUGAL' AND instr(coalesce(rls_country_token, ''), '|PORTUGAL|') > 0 THEN 'COUNTRY_ALL'
    ELSE 'PLATFORM_COUNTRY'
  END AS rls_access_type,
  current_timestamp() AS _processed_at
FROM r2;

-- Pares (utilizador, registo) para os acessos NÃO globais.
-- Os acessos GLOBAL são tratados diretamente na view (evita multiplicar linhas).
CREATE OR REPLACE TABLE ${catalog}.silver.pipeline_user_access AS
SELECT DISTINCT a.rls_email, p.record_id
FROM ${catalog}.silver.rls_user_access a
JOIN ${catalog}.silver.pipeline p
  ON (    a.rls_access_type = 'COUNTRY_ALL'
      AND p.rls_match_country = 'PORTUGAL')
  OR (    a.rls_access_type = 'PLATFORM_COUNTRY'
      AND a.rls_match_platform = p.rls_match_platform
      AND p.rls_match_country IS NOT NULL
      AND instr(coalesce(a.rls_country_token, ''), concat('|', p.rls_match_country, '|')) > 0)
WHERE a.rls_email IS NOT NULL;

-- Mesma regra aplicada aos Leads (por plataforma/país do próprio lead, porque os
-- LeadId de DEV não existem no Pipeline de PRD)
CREATE OR REPLACE TABLE ${catalog}.silver.leads_user_access AS
SELECT DISTINCT a.rls_email, l.source_env, l.record_id
FROM ${catalog}.silver.rls_user_access a
JOIN ${catalog}.silver.leads l
  ON (    a.rls_access_type = 'COUNTRY_ALL'
      AND l.rls_match_country = 'PORTUGAL')
  OR (    a.rls_access_type = 'PLATFORM_COUNTRY'
      AND a.rls_match_platform = l.rls_match_platform
      AND l.rls_match_country IS NOT NULL
      AND instr(coalesce(a.rls_country_token, ''), concat('|', l.rls_match_country, '|')) > 0)
WHERE a.rls_email IS NOT NULL;

-- Reconciliação de acessos (tabela calculada SEC_AccessReconciliation)
CREATE OR REPLACE TABLE ${catalog}.silver.sec_access_reconciliation AS
WITH prof AS (
  SELECT platform, country, rls_match_platform, rls_country_token, rls_access_type, COUNT(*) AS users
  FROM ${catalog}.silver.rls_user_access
  GROUP BY platform, country, rls_match_platform, rls_country_token, rls_access_type
),
tot AS (
  SELECT COUNT(*) AS all_rows,
         SUM(CASE WHEN rls_match_country = 'PORTUGAL' THEN 1 ELSE 0 END) AS pt_rows
  FROM ${catalog}.silver.pipeline
),
pc AS (
  SELECT prof.platform, prof.country, prof.rls_match_platform, prof.rls_country_token, prof.rls_access_type,
         COUNT(p.record_id)                  AS pc_rows,
         COUNT(DISTINCT p.rls_match_country) AS pc_countries
  FROM prof
  LEFT JOIN ${catalog}.silver.pipeline p
    ON  prof.rls_access_type = 'PLATFORM_COUNTRY'
    AND p.rls_match_platform = prof.rls_match_platform
    AND p.rls_match_country IS NOT NULL
    AND instr(coalesce(prof.rls_country_token, ''), concat('|', p.rls_match_country, '|')) > 0
  GROUP BY prof.platform, prof.country, prof.rls_match_platform, prof.rls_country_token, prof.rls_access_type
),
m AS (
  SELECT
    prof.platform, prof.country, prof.rls_match_platform, prof.rls_country_token, prof.rls_access_type, prof.users,
    CASE prof.rls_access_type WHEN 'GLOBAL' THEN NULL WHEN 'COUNTRY_ALL' THEN 1
         ELSE 1 + length(coalesce(prof.country, '')) - length(replace(coalesce(prof.country, ''), '/', '')) END AS expected_countries,
    CASE prof.rls_access_type WHEN 'GLOBAL' THEN tot.all_rows WHEN 'COUNTRY_ALL' THEN tot.pt_rows
         ELSE pc.pc_rows END AS pipeline_rows,
    CASE prof.rls_access_type WHEN 'GLOBAL' THEN NULL
         WHEN 'COUNTRY_ALL' THEN CASE WHEN tot.pt_rows > 0 THEN 1 ELSE 0 END
         ELSE pc.pc_countries END AS matched_countries
  FROM prof
  CROSS JOIN tot
  LEFT JOIN pc
    ON  pc.rls_access_type = prof.rls_access_type
    AND coalesce(pc.platform, '') = coalesce(prof.platform, '')
    AND coalesce(pc.country, '')  = coalesce(prof.country, '')
)
SELECT
  m.*,
  CASE
    WHEN rls_access_type = 'GLOBAL'           AND pipeline_rows > 0 THEN 'OK - Global'
    WHEN rls_access_type = 'COUNTRY_ALL'      AND pipeline_rows > 0 THEN 'OK - All Country'
    WHEN rls_access_type = 'PLATFORM_COUNTRY' AND pipeline_rows > 0 AND expected_countries = matched_countries THEN 'OK'
    ELSE 'CHECK'
  END AS status,
  current_timestamp() AS _processed_at
FROM m;
