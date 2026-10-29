# Databricks notebook source
# MAGIC %md
# MAGIC # Executar um ficheiro SQL do projeto
# MAGIC Lê `sql/<sql_file>`, substitui os `${parametros}` pelos parâmetros do job e executa
# MAGIC cada instrução com `spark.sql`. Usado por várias tarefas do job **CRM Reporting - ETL**.

# COMMAND ----------
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from crm_etl.sqltext import render, split_statements, strip_engine_blocks  # noqa: E402

PARAMS = ["sql_file", "catalog", "source_catalog", "leads_source_active", "admin_group",
          "leads_env", "leads_catalog"]
params = {}
for p in PARAMS:
    try:
        params[p] = dbutils.widgets.get(p)  # noqa: F821
    except Exception:
        pass
print("Parâmetros:", {k: v for k, v in params.items()})

sql_path = Path(os.getcwd()).parent / "sql" / params["sql_file"]
sql = strip_engine_blocks(render(sql_path.read_text(encoding="utf-8"), params))

# COMMAND ----------
for i, stmt in enumerate(split_statements(sql), 1):
    first = next(l for l in stmt.splitlines() if l.strip() and not l.strip().startswith("--"))
    print(f"[{i}] {first.strip()[:110]}")
    spark.sql(stmt)  # noqa: F821
print("Concluído:", params["sql_file"])
