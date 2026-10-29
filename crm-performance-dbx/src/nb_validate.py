# Databricks notebook source
# MAGIC %md
# MAGIC # Validações pós-carga
# MAGIC Executa `sql/90_validation.sql`. O job FALHA se alguma verificação tiver estado `FAIL`
# MAGIC (as `WARN` ficam apenas registadas). Os resultados ficam em `<catalog>.ref.validation_log`.

# COMMAND ----------
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from crm_etl.sqltext import render, split_statements  # noqa: E402

catalog = dbutils.widgets.get("catalog")  # noqa: F821
sql = render((Path(os.getcwd()).parent / "sql" / "90_validation.sql").read_text(encoding="utf-8"),
             {"catalog": catalog})
stmts = split_statements(sql)
for s in stmts[:-1]:
    spark.sql(s)  # noqa: F821
res = spark.sql(stmts[-1])  # noqa: F821
display(res)  # noqa: F821
rows = res.collect()
fails = [r for r in rows if r["status"] == "FAIL"]
if fails:
    raise AssertionError("Validações falhadas: " + "; ".join(f"{r['check_name']}={r['value']}" for r in fails))
print("Todas as validações críticas passaram.")
