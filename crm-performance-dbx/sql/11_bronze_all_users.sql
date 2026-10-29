-- =============================================================================
-- 11_bronze_all_users.sql  (job diário - OPCIONAL)
-- No PBI a tabela "User_Access" estava COLADA no modelo (Json/Binary embutido),
-- portanto NUNCA era atualizada. A query original (página oculta "Notes") lia
-- crm.vAllUsers. Aqui passa a ser lida diretamente da fonte.
-- Se crm.vAllUsers não estiver acessível pelo foreign catalog, desative esta
-- tarefa no job e carregue o CSV via src/load_files_from_volume.py (modo "users").
-- =============================================================================
-- NOTA: a query original não devolvia "LoginsDone"; o PBI tinha essa coluna nos
-- dados colados. Confirme as colunas reais de crm.vAllUsers e ajuste
-- 21_silver_other.sql (tabela silver.crm_users) se necessário.
CREATE OR REPLACE TABLE ${catalog}.bronze.crm_all_users AS
SELECT *, current_timestamp() AS _ingested_at
FROM ${source_catalog}.crm.vAllUsers;
