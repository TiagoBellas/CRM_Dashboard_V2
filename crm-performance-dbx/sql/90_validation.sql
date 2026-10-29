-- =============================================================================
-- 90_validation.sql  (última tarefa do job)
-- Verificações automáticas. status: PASS | WARN | FAIL (FAIL faz o job falhar).
-- A última instrução (SELECT) é a que devolve o resultado.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ${catalog}.ref.validation_log (
  run_ts TIMESTAMP, check_name STRING, status STRING, value DOUBLE, detail STRING
);

INSERT INTO ${catalog}.ref.validation_log
SELECT current_timestamp(), check_name, status, value, detail FROM (
  SELECT 'pipeline_rows' AS check_name,
         CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END AS status,
         CAST(COUNT(*) AS DOUBLE) AS value, 'Linhas em silver.pipeline' AS detail
  FROM ${catalog}.silver.pipeline
  UNION ALL
  SELECT 'pipeline_duplicate_record_id',
         CASE WHEN COUNT(*) - COUNT(DISTINCT record_id) = 0 THEN 'PASS' ELSE 'FAIL' END,
         CAST(COUNT(*) - COUNT(DISTINCT record_id) AS DOUBLE), 'RecordId tem de ser único (chave da RLS)'
  FROM ${catalog}.silver.pipeline
  UNION ALL
  SELECT 'rls_users',
         CASE WHEN COUNT(DISTINCT rls_email) > 0 THEN 'PASS' ELSE 'FAIL' END,
         CAST(COUNT(DISTINCT rls_email) AS DOUBLE), 'Utilizadores na lista de acessos'
  FROM ${catalog}.silver.rls_user_access
  UNION ALL
  SELECT 'rls_profiles_to_check',
         CASE WHEN SUM(CASE WHEN status = 'CHECK' THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'WARN' END,
         CAST(SUM(CASE WHEN status = 'CHECK' THEN 1 ELSE 0 END) AS DOUBLE),
         'Perfis de acesso sem correspondência no pipeline (ver página Administração)'
  FROM ${catalog}.silver.sec_access_reconciliation
  UNION ALL
  SELECT 'leads_active_source_rows',
         CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END, CAST(COUNT(*) AS DOUBLE),
         'Leads na origem ativa (ref.app_config.leads_source_active)'
  FROM ${catalog}.gold.vw_leads_all WHERE is_active_source = 1
  UNION ALL
  SELECT 'leads_active_source_match_pipeline',
         CASE WHEN max(pct_matching_pipeline) > 0 THEN 'PASS' ELSE 'WARN' END,
         CAST(max(pct_matching_pipeline) AS DOUBLE),
         'Percentagem de LeadId da origem ativa que existem no pipeline (0 = origem DEV, ver A1)'
  FROM ${catalog}.gold.vw_leads_source_comparison WHERE is_active_source = 1
  UNION ALL
  SELECT 'dq_critical_items',
         CASE WHEN SUM(CASE WHEN dq_severity = 'Critical' THEN 1 ELSE 0 END) = 0 THEN 'PASS' ELSE 'WARN' END,
         CAST(SUM(CASE WHEN dq_severity = 'Critical' THEN 1 ELSE 0 END) AS DOUBLE),
         'Registos com problemas críticos de classificação na fonte'
  FROM ${catalog}.silver.pipeline
  UNION ALL
  SELECT 'bronze_fresh_today',
         CASE WHEN CAST(max(_ingested_at) AS DATE) = current_date() THEN 'PASS' ELSE 'FAIL' END,
         CAST(datediff(current_date(), CAST(max(_ingested_at) AS DATE)) AS DOUBLE),
         'Dias desde a última ingestão do pipeline'
  FROM ${catalog}.bronze.crm_deal_pipeline
) c;

SELECT check_name, status, value, detail
FROM ${catalog}.ref.validation_log
WHERE run_ts = (SELECT max(run_ts) FROM ${catalog}.ref.validation_log)
ORDER BY CASE status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, check_name;
