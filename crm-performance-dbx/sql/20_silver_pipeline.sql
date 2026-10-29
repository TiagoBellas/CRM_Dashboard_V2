-- =============================================================================
-- 20_silver_pipeline.sql  (job diário)
-- Tabela silver.pipeline = tabela "Pipeline" do Power BI:
--   (1) todos os passos do Power Query (renomeações, substituições, segmentos)
--   (2) todas as colunas calculadas DAX que NÃO dependem de TODAY()
--       (as que dependem de TODAY() ficam na view gold.vw_pipeline_all)
--   (3) colunas auxiliares do funil (substituem as medidas DAX iterativas)
--
-- REGRAS DE TRADUÇÃO DAX -> SQL (importante para quem mantiver este código):
--   * DAX compara texto SEM distinguir maiúsculas ("Lead" = "LEAD"). Em SQL é
--     sensível, por isso todas as comparações usam upper(...).
--   * Em DAX, BLANK <> "Lost" é VERDADEIRO; em SQL NULL <> 'Lost' é NULL.
--     Por isso usamos coalesce(x, '') nas desigualdades.
--   * TRIM(SUBSTITUTE(x, UNICHAR(160), " ")) -> nullif(trim(replace(x, chr(160), ' ')), '')
-- =============================================================================

CREATE OR REPLACE TABLE ${catalog}.silver.pipeline
COMMENT 'Pipeline de Leads e Deals do CRM com regras do Power BI (PQ + colunas DAX)'
AS
WITH
-- ---------------------------------------------------------------------------
-- (1) Power Query
-- ---------------------------------------------------------------------------
pq AS (
  SELECT
    b.RecordType                                       AS record_type,
    b.RecordId                                         AS record_id,
    b.DealId                                           AS deal_id,
    b.LeadId                                           AS lead_id,
    b.SourceSystem                                     AS source_system,
    b.EntityName                                       AS entity_name,
    b.Name                                             AS record_name,
    CAST(b.CreatedOn   AS TIMESTAMP)                   AS created_on,
    CAST(b.ModifiedOn  AS TIMESTAMP)                   AS modified_on,
    CAST(b.ClosedOn    AS TIMESTAMP)                   AS closed_on,
    CAST(b.PassedToNBO AS TIMESTAMP)                   AS passed_to_nbo,
    CAST(b.PassedToDD  AS TIMESTAMP)                   AS passed_to_dd,
    CAST(b.PassedToIC  AS TIMESTAMP)                   AS passed_to_ic,
    CAST(b.PassedToWon AS TIMESTAMP)                   AS passed_to_won,
    b.StateName                                        AS state_name,
    b.StatusName                                       AS status_name,
    -- #"Replaced Value": "Closed" -> "Won" em ActiveStage
    replace(b.ActiveStage, 'Closed', 'Won')            AS active_stage,
    -- #"Replaced Value1": "NBO Stage" -> "NBO / Preliminary Bids"
    replace(b.LastDealStatus, 'NBO Stage', 'NBO / Preliminary Bids') AS last_deal_status,
    b.ClosureReason                                    AS closure_reason,
    b.Segment                                          AS segment_source,
    -- #"Extracted Text After Delimiter": texto depois do ÚLTIMO " - "
    CASE WHEN instr(b.Segment, ' - ') > 0
         THEN regexp_extract(b.Segment, '^.* - (.*)$', 1)
         ELSE '' END                                   AS segment_extracted,
    b.Platform                                         AS platform_source,
    -- #"Replaced Value2..7": remove sufixos societários (+ trim, ver doc 02)
    trim(replace(replace(replace(replace(replace(
         b.Platform, 'SpA', ''), ', SA', ''), 'Ltd', ''), 'BV', ''), ', Lda', '')) AS platform_cleaned,
    b.Template                                         AS vertical,      -- renomeado no PQ
    b.CentralMD                                        AS central_md,    -- renomeado no PQ
    b.FundName                                         AS fund_name,
    b.CountryName                                      AS country_name,
    b.OriginatorName                                   AS originator,    -- renomeado no PQ
    b.Seller                                           AS seller,
    b.OwnerName                                        AS owner_name,
    CAST(b.AmountBase   AS DOUBLE)                     AS amount_base,
    b.CurrencyName                                     AS currency_name,
    CAST(b.ExchangeRate AS DOUBLE)                     AS exchange_rate,
    CAST(b.AmountInEuro AS DOUBLE)                     AS amount_eur,
    b.LeadStatus                                       AS lead_status,
    b.DescriptionText                                  AS description_text,
    b.PlatformId                                       AS platform_id
  FROM ${catalog}.bronze.crm_deal_pipeline b
),

-- Segmento final (mapeamento) e Platform final ("" -> "Other")
pq2 AS (
  SELECT
    pq.*,
    coalesce(sm.segment_name, 'Other')                 AS segment,
    CASE WHEN pq.platform_cleaned = '' THEN 'Other' ELSE pq.platform_cleaned END AS platform
  FROM pq
  LEFT JOIN ${catalog}.ref.segment_mapping sm
    ON sm.source_value = pq.segment_extracted
),

-- Versões normalizadas usadas nas regras DAX
n AS (
  SELECT
    pq2.*,
    nullif(trim(replace(active_stage,     chr(160), ' ')), '') AS n_active,
    nullif(trim(replace(last_deal_status, chr(160), ' ')), '') AS n_last,
    nullif(trim(replace(lead_status,      chr(160), ' ')), '') AS n_lead_status,
    nullif(trim(replace(state_name,       chr(160), ' ')), '') AS n_state,
    nullif(trim(replace(status_name,      chr(160), ' ')), '') AS n_status,
    nullif(trim(replace(record_type,      chr(160), ' ')), '') AS n_record_type,
    nullif(trim(replace(source_system,    chr(160), ' ')), '') AS n_source,
    nullif(trim(replace(closure_reason,   chr(160), ' ')), '') AS n_closure,
    nullif(trim(entity_name), '')                              AS n_entity,
    replace(replace(deal_id, '{', ''), '}', '')                AS deal_guid,
    replace(replace(lead_id, '{', ''), '}', '')                AS lead_guid
  FROM pq2
),

-- ---------------------------------------------------------------------------
-- (2) Colunas calculadas DAX - 1ª camada
-- ---------------------------------------------------------------------------
c1 AS (
  SELECT
    n.*,
    -- flags reutilizadas
    (upper(n_active) = 'LEAD' AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0) AS f_lead_rejected_contains,
    (upper(n_active) = 'LEAD' AND upper(coalesce(n_lead_status, '')) = 'REJECTED')          AS f_lead_rejected_exact,

    -- [Stage Snapshot] (nome, antes de juntar o índice)
    CASE
      WHEN upper(n_active) = 'LEAD' AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0 THEN 'Lead'
      WHEN upper(n_active) = 'LOST' THEN
           CASE WHEN upper(coalesce(n_last, '')) <> 'LOST' THEN coalesce(n_last, 'Early Prospect')
                ELSE 'Early Prospect' END
      WHEN n_active IS NULL THEN 'Lead'
      ELSE n_active
    END AS stage_snapshot_name,

    -- [Terminal Snapshot]  (idêntica a [Terminal Snapshot v2])
    CASE
      WHEN upper(n_active) = 'LEAD' AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0 THEN 'Lost'
      WHEN upper(n_active) = 'WON'  OR upper(n_state) = 'WON'  THEN 'Won'
      WHEN upper(n_active) = 'LOST' OR upper(n_state) = 'LOST' THEN 'Lost'
      ELSE 'Active'
    END AS terminal_snapshot,

    -- [Terminal Snapshot 2]
    CASE
      WHEN upper(n_active) = 'LEAD' AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0 THEN 'Lost'
      WHEN upper(n_active) = 'LOST'
        OR (upper(n_record_type) = 'DEAL' AND upper(n_source) = 'CRM' AND upper(n_state) = 'LOST') THEN 'Lost'
      WHEN upper(n_active) = 'WON' THEN 'Won'
      ELSE 'Active'
    END AS terminal_snapshot_2,

    -- [Decomp Closure Reason]
    CASE
      WHEN upper(n_active) = 'LEAD' AND upper(coalesce(n_lead_status, '')) = 'REJECTED' THEN 'Rejected'
      WHEN upper(n_active) = 'LOST' THEN coalesce(n_closure, 'Unassigned')
      ELSE NULL
    END AS decomp_closure_reason,

    -- [DQ Expected Terminal]
    CASE
      WHEN upper(coalesce(n_record_type, '')) = 'LEAD'
           AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0 THEN 'Lost'
      WHEN upper(coalesce(n_active, '')) = 'WON'  OR upper(coalesce(n_state, '')) = 'WON'  THEN 'Won'
      WHEN upper(coalesce(n_active, '')) = 'LOST' OR upper(coalesce(n_state, '')) = 'LOST' THEN 'Lost'
      ELSE 'Active'
    END AS dq_expected_terminal,

    -- flags para [DQ Expected Stage Name]
    (upper(coalesce(n_record_type, '')) = 'LEAD'
       AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0)                     AS f_dq_rejected_lead,
    (upper(coalesce(n_record_type, '')) = 'DEAL'
       AND (upper(coalesce(n_active, '')) = 'LOST' OR upper(coalesce(n_state, '')) = 'LOST')) AS f_dq_lost_deal,

    -- ---- Funil (substitui as medidas "1. Active", "Lost Amount (At Stage) €", "Lost Deals Count")
    (   upper(coalesce(n_active, ''))      = 'LOST'
     OR upper(coalesce(n_state, ''))       = 'LOST'
     OR upper(coalesce(n_lead_status, '')) IN ('REJECTED', 'PLATFORM REJECTED')
     OR upper(coalesce(n_last, ''))        = 'LOST')                                      AS funnel_is_lost
  FROM n
),

c2 AS (
  SELECT
    c1.*,
    -- stage "alcançado" (medida 1. Active / 1. Active Amount €)
    CASE
      WHEN upper(coalesce(n_last, '')) = 'LOST'      THEN 'Early Prospect'
      WHEN funnel_is_lost AND n_last IS NOT NULL      THEN n_last
      WHEN funnel_is_lost                             THEN 'Lead'
      WHEN n_active IS NOT NULL                       THEN n_active
      ELSE 'Lead'
    END AS funnel_reached_stage_name,
    -- stage onde foi perdido (medida Lost Amount (At Stage) €)
    CASE WHEN funnel_is_lost THEN
      CASE WHEN upper(coalesce(n_last, '')) = 'LOST' THEN 'Early Prospect' ELSE coalesce(n_last, 'Lead') END
    END AS funnel_lost_stage_name_amount,
    -- stage onde foi perdido (medida Lost Deals Count)
    CASE
      WHEN upper(coalesce(n_active, '')) = 'LEAD'
           AND upper(coalesce(n_lead_status, '')) IN ('REJECTED', 'PLATFORM REJECTED') THEN 'Lead'
      WHEN upper(coalesce(n_last, '')) = 'LOST'                                         THEN 'Early Prospect'
      WHEN upper(coalesce(n_active, '')) = 'LOST'                                       THEN coalesce(n_last, 'Early Prospect')
      ELSE NULL
    END AS funnel_lost_stage_name_count
  FROM c1
),

-- Lookups ao _DimStage (LOOKUPVALUE do DAX, sem distinguir maiúsculas)
c3 AS (
  SELECT
    c2.*,
    ds_snap.stage_index                        AS snap_idx,
    ds_last.stage_index                        AS last_idx,
    ds_act.stage_index                         AS active_idx,
    coalesce(ds_reach.stage_index, 0)          AS funnel_reached_stage_index,
    ds_lost_a.stage_index                      AS funnel_lost_stage_index_amount,
    ds_lost_c.stage_index                      AS funnel_lost_stage_index_count
  FROM c2
  LEFT JOIN ${catalog}.ref.dim_stage ds_snap   ON upper(ds_snap.stage_name)   = upper(c2.stage_snapshot_name)
  LEFT JOIN ${catalog}.ref.dim_stage ds_last   ON upper(ds_last.stage_name)   = upper(coalesce(c2.n_last, ''))
  LEFT JOIN ${catalog}.ref.dim_stage ds_act    ON upper(ds_act.stage_name)    = upper(coalesce(c2.n_active, ''))
  LEFT JOIN ${catalog}.ref.dim_stage ds_reach  ON upper(ds_reach.stage_name)  = upper(c2.funnel_reached_stage_name)
  LEFT JOIN ${catalog}.ref.dim_stage ds_lost_a ON upper(ds_lost_a.stage_name) = upper(c2.funnel_lost_stage_name_amount)
  LEFT JOIN ${catalog}.ref.dim_stage ds_lost_c ON upper(ds_lost_c.stage_name) = upper(c2.funnel_lost_stage_name_count)
),

c4 AS (
  SELECT
    c3.*,
    -- [Stage Snapshot] = índice & ". " & nome
    concat(coalesce(CAST(snap_idx AS STRING), ''), '. ', stage_snapshot_name) AS stage_snapshot,
    -- [DQ Expected Stage Name]
    CASE
      WHEN f_dq_rejected_lead THEN 'Lead'
      WHEN f_dq_lost_deal AND last_idx IS NOT NULL
           AND upper(coalesce(n_last, '')) NOT IN ('LOST', 'WON') THEN coalesce(n_last, '')
      WHEN f_dq_lost_deal AND active_idx IS NOT NULL
           AND upper(coalesce(n_active, '')) NOT IN ('LOST', 'WON') THEN coalesce(n_active, '')
      WHEN f_dq_lost_deal THEN 'Early Prospect'
      WHEN coalesce(n_active, '') = '' THEN 'Lead'
      ELSE n_active
    END AS dq_expected_stage_name
  FROM c3
),

c5 AS (
  SELECT
    c4.*,
    ds_snap2.stage_index AS stage_snapshot_index,          -- [Stage Snapshot Index]
    CASE WHEN ds_exp.stage_index IS NOT NULL
         THEN concat(CAST(ds_exp.stage_index AS STRING), '. ', c4.dq_expected_stage_name)
         ELSE c4.dq_expected_stage_name END AS dq_expected_stage_snapshot
  FROM c4
  LEFT JOIN ${catalog}.ref.dim_stage ds_snap2 ON ds_snap2.stage_display = c4.stage_snapshot
  LEFT JOIN ${catalog}.ref.dim_stage ds_exp   ON upper(ds_exp.stage_name) = upper(c4.dq_expected_stage_name)
),

c6 AS (
  SELECT
    c5.*,
    CASE WHEN upper(coalesce(record_type, '')) = 'LEAD'
              AND instr(upper(coalesce(n_lead_status, '')), 'REJECTED') > 0
              AND upper(terminal_snapshot) <> 'LOST' THEN 1 ELSE 0 END          AS dq_lead_rejected_issue,
    CASE WHEN upper(coalesce(record_type, '')) = 'DEAL'
              AND upper(coalesce(n_state, '')) = 'LOST'
              AND upper(terminal_snapshot) <> 'LOST' THEN 1 ELSE 0 END          AS dq_deal_lost_issue,
    CASE WHEN dq_expected_terminal = 'Lost'
              AND coalesce(stage_snapshot, '') <> coalesce(dq_expected_stage_snapshot, '')
         THEN 1 ELSE 0 END                                                      AS dq_stage_classification_issue,
    CASE WHEN upper(coalesce(record_type, '')) = 'DEAL'
              AND upper(coalesce(n_state, '')) = 'LOST'
              AND upper(coalesce(n_active, '')) <> 'LOST' THEN 1 ELSE 0 END     AS dq_source_state_conflict,
    -- DAX: [AmountInEuro] = BLANK() é VERDADEIRO também para 0 (BLANK = 0 em comparações)
    CASE WHEN amount_eur IS NULL OR amount_eur = 0 THEN 1 ELSE 0 END           AS dq_amount
  FROM c5
)

-- ---------------------------------------------------------------------------
-- Projeção final
-- ---------------------------------------------------------------------------
SELECT
  -- identificação
  record_type, record_id, deal_id, lead_id,
  coalesce(record_id, deal_id, lead_id)                       AS record_key,
  source_system, entity_name, record_name,
  -- datas
  created_on, modified_on, closed_on,
  passed_to_nbo, passed_to_dd, passed_to_ic, passed_to_won,
  -- estado
  state_name, status_name, active_stage, last_deal_status, lead_status, closure_reason,
  -- dimensões
  segment, segment_source, platform, platform_source, vertical, central_md, fund_name,
  country_name, originator, seller, owner_name, platform_id,
  -- valores
  amount_base, currency_name, exchange_rate, amount_eur, description_text,

  -- ===== colunas calculadas DAX =====
  stage_snapshot,
  stage_snapshot_index,
  terminal_snapshot,
  terminal_snapshot                                           AS terminal_snapshot_v2,
  terminal_snapshot_2,
  decomp_closure_reason,

  -- [CRM Record URL]
  CASE
    WHEN n_entity = 'Deal' AND length(coalesce(deal_guid, '')) > 0 THEN concat(cfg_url.config_value, '&forceUCI=1&pagetype=entityrecord&etn=', n_entity, '&id=', deal_guid, '&formid=', cfg_form.config_value)
    WHEN n_entity = 'Lead' AND length(coalesce(lead_guid, '')) > 0 THEN concat(cfg_url.config_value, '&forceUCI=1&pagetype=entityrecord&etn=', n_entity, '&id=', lead_guid)
    WHEN length(coalesce(deal_guid, '')) > 0 THEN concat(cfg_url.config_value, '&forceUCI=1&pagetype=entityrecord&etn=', coalesce(n_entity, ''), '&id=', deal_guid, '&formid=', cfg_form.config_value)
    WHEN length(coalesce(lead_guid, '')) > 0 THEN concat(cfg_url.config_value, '&forceUCI=1&pagetype=entityrecord&etn=', coalesce(n_entity, ''), '&id=', lead_guid)
    ELSE NULL
  END                                                         AS crm_record_url,

  -- Datas de calendário (Month Start, Quarter ...)
  CAST(make_date(year(created_on), month(created_on), 1) AS DATE)            AS month_start,
  concat(
    CASE month(created_on) WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Apr'
                           WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug'
                           WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN 12 THEN 'Dec' END,
    ' ', CAST(year(created_on) AS STRING))                                   AS month_year,
  CAST(floor((month(created_on) - 1) / 3) AS INT) + 1                        AS quarter_number,
  CAST(make_date(year(created_on), (CAST(floor((month(created_on) - 1) / 3) AS INT)) * 3 + 1, 1) AS DATE) AS quarter_start,
  concat('Q', CAST(CAST(floor((month(created_on) - 1) / 3) AS INT) + 1 AS STRING), '-', CAST(year(created_on) AS STRING)) AS quarter_label,
  concat('Q', CAST(CAST(floor((month(created_on) - 1) / 3) AS INT) + 1 AS STRING), ' ', CAST(year(created_on) AS STRING)) AS quarter_year,
  year(created_on) * 10 + CAST(floor((month(created_on) - 1) / 3) AS INT) + 1 AS quarter_sort,

  -- Qualidade de dados
  dq_expected_terminal,
  dq_expected_stage_name,
  dq_expected_stage_snapshot,
  dq_lead_rejected_issue,
  dq_deal_lost_issue,
  dq_stage_classification_issue,
  dq_source_state_conflict,
  CASE WHEN dq_lead_rejected_issue = 1 OR dq_deal_lost_issue = 1
         OR dq_stage_classification_issue = 1 OR dq_source_state_conflict = 1 THEN 1 ELSE 0 END AS dq_has_classification_issue,
  CASE
    WHEN dq_lead_rejected_issue = 1        THEN 'Rejected Lead classified as Active'
    WHEN dq_deal_lost_issue = 1            THEN 'Lost Deal classified as Active'
    WHEN dq_stage_classification_issue = 1 THEN 'Lost Deal assigned to incorrect Stage'
    WHEN dq_source_state_conflict = 1      THEN 'Source status conflicts with Active Stage'
  END                                                         AS dq_primary_issue,
  CASE
    WHEN dq_lead_rejected_issue = 1 OR dq_deal_lost_issue = 1               THEN 'Critical'
    WHEN dq_stage_classification_issue = 1 OR dq_source_state_conflict = 1 THEN 'High'
  END                                                         AS dq_severity,
  concat(
    CASE WHEN dq_lead_rejected_issue = 1        THEN 'Lead is rejected but currently classified as Active. ' ELSE '' END,
    CASE WHEN dq_deal_lost_issue = 1            THEN 'Deal is marked Lost in the source but currently classified as Active. ' ELSE '' END,
    CASE WHEN dq_stage_classification_issue = 1 THEN 'The Stage does not represent the expected stage at which the deal was lost. ' ELSE '' END,
    CASE WHEN dq_source_state_conflict = 1      THEN 'Source State and Active Stage contain conflicting information. ' ELSE '' END
  )                                                           AS dq_issue_description,
  dq_amount,

  -- RLS (colunas "RLS Match Platform / Country / Scope")
  CASE WHEN upper(trim(replace(coalesce(platform, ''), chr(160), ' '))) = '' THEN NULL
       ELSE coalesce(pa.rls_platform, upper(trim(replace(coalesce(platform, ''), chr(160), ' ')))) END AS rls_match_platform,
  nullif(upper(trim(replace(coalesce(country_name, ''), chr(160), ' '))), '')                        AS rls_match_country,

  -- Funil
  funnel_is_lost,
  funnel_reached_stage_index,
  funnel_lost_stage_index_amount,
  funnel_lost_stage_index_count,

  -- campos normalizados usados pelas colunas dependentes de TODAY() (view gold)
  n_active, n_last, n_lead_status, n_state, n_status,

  current_timestamp()                                         AS _processed_at
FROM c6
LEFT JOIN ${catalog}.ref.platform_rls_alias pa
  ON pa.platform_upper = upper(trim(replace(coalesce(c6.platform, ''), chr(160), ' ')))
CROSS JOIN (SELECT config_value FROM ${catalog}.ref.app_config WHERE config_key = 'crm_base_url')     cfg_url
CROSS JOIN (SELECT config_value FROM ${catalog}.ref.app_config WHERE config_key = 'crm_deal_form_id') cfg_form;
