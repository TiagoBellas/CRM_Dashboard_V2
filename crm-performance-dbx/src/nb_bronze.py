# Databricks notebook source
# MAGIC %md
# MAGIC # Camada bronze
# MAGIC * `source_mode = federation` → copia as views do Synapse (Lakehouse Federation)
# MAGIC * `source_mode = sample`     → carrega os CSV sintéticos de `/Volumes/<catalog>/ref/landing/sample/`
# MAGIC
# MAGIC **Leads DEV e PRD (achado A1):** ambas as versões são ingeridas. Se a versão *ativa*
# MAGIC (`leads_source_active`) falhar o job falha; se falhar só a versão inativa, fica um aviso.

# COMMAND ----------
# MAGIC %pip install openpyxl --quiet

# COMMAND ----------
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.getcwd())
from crm_etl.sqltext import render, split_statements, strip_engine_blocks  # noqa: E402


def w(name, default=None):
    try:
        return dbutils.widgets.get(name)  # noqa: F821
    except Exception:
        return default


catalog = w("catalog")
mode = (w("source_mode", "federation") or "federation").lower()
active = (w("leads_source_active", "DEV") or "DEV").upper()
SQL = Path(os.getcwd()).parent / "sql"


def run_sql_file(name, **extra):
    params = {"catalog": catalog, "source_catalog": w("source_catalog"), **extra}
    sql = strip_engine_blocks(render((SQL / name).read_text(encoding="utf-8"), params))
    for stmt in split_statements(sql):
        spark.sql(stmt)  # noqa: F821
    print("OK", name, extra or "")


warnings = []

# COMMAND ----------
if mode == "federation":
    run_sql_file("10_bronze_ingest.sql")
    try:
        run_sql_file("11_bronze_all_users.sql")
    except Exception as exc:  # opcional
        warnings.append(f"crm.vAllUsers indisponível ({exc.__class__.__name__}); página DMS Usage sem lista de utilizadores.")
    for env, cat in (("PRD", w("leads_prd_catalog")), ("DEV", w("leads_dev_catalog"))):
        try:
            if not cat:
                raise ValueError(f"parâmetro leads_{env.lower()}_catalog vazio")
            run_sql_file("12_bronze_leads.sql", leads_env=env, leads_catalog=cat)
        except Exception as exc:
            if env == active:
                raise RuntimeError(f"Falhou a ingestão dos Leads {env}, que é a origem ATIVA.") from exc
            warnings.append(f"Leads {env} (inativa) não ingerida: {exc}")
elif mode == "sample":
    base = f"/Volumes/{catalog}/ref/landing/sample"
    dates = {"crm_deal_pipeline": ["CreatedOn", "ModifiedOn", "ClosedOn", "PassedToNBO", "PassedToDD", "PassedToIC", "PassedToWon"],
             "crm_leads": ["CreatedOn", "ModifiedOn", "ClosedOn"],
             "crm_user_access_platform": ["MonthStart", "LastAccessInMonthUtc"]}
    for name in ["crm_deal_pipeline", "investment_allocation", "crm_user_access_platform", "crm_all_users", "crm_leads"]:
        pdf = pd.read_csv(f"{base}/{name}.csv", parse_dates=dates.get(name, []), dtype={"LastLogin": str})
        pdf = pdf.astype(object).where(pdf.notna(), None)
        sdf = spark.createDataFrame(pdf)  # noqa: F821
        from pyspark.sql import functions as F
        sdf = sdf.withColumn("_ingested_at", F.current_timestamp())
        sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{catalog}.bronze.{name}")
        print("OK sample", name, sdf.count())
else:
    raise ValueError(f"source_mode inválido: {mode}")

for msg in warnings:
    print("AVISO:", msg)
