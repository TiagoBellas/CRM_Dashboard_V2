# Databricks notebook source
# MAGIC %md
# MAGIC # Carregar a lista de acessos RLS
# MAGIC Substitui a ligação do Power BI ao Excel local
# MAGIC `C:\Users\...\UserPlatformCountry 1.xlsx` (achado A2).
# MAGIC
# MAGIC **Como atualizar os acessos:** carregar a nova versão do ficheiro (Excel com a folha
# MAGIC *Active Users Consuming Licenses*, ou CSV com as mesmas colunas) para
# MAGIC `/Volumes/<catalog>/ref/landing/rls/`. O job usa sempre o ficheiro mais recente.

# COMMAND ----------
# MAGIC %pip install openpyxl --quiet

# COMMAND ----------
import os
import sys

sys.path.insert(0, os.getcwd())
from crm_etl.rls import read_raw, transform  # noqa: E402

catalog = dbutils.widgets.get("catalog")  # noqa: F821
folder = f"/Volumes/{catalog}/ref/landing/rls"
files = [f for f in dbutils.fs.ls(folder) if f.name.lower().endswith((".xlsx", ".xlsm", ".csv"))]  # noqa: F821
if not files:
    raise FileNotFoundError(f"Nenhum ficheiro RLS em {folder}. Carregue UserPlatformCountry.xlsx (ver guia, Fase 7).")
latest = max(files, key=lambda f: f.modificationTime)
print("A usar:", latest.path)
df = transform(read_raw(latest.path.replace("dbfs:", "")))
if df["primary_email"].isna().all():
    raise ValueError("O ficheiro RLS não tem e-mails preenchidos.")

# COMMAND ----------
sdf = spark.createDataFrame(df.astype(str).where(df.notna(), None),  # noqa: F821
                            "user_id string, full_name string, platform string, country string, primary_email string")
(sdf.write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{catalog}.ref.rls_user_access_raw"))
print(f"{sdf.count()} linhas gravadas em {catalog}.ref.rls_user_access_raw")
