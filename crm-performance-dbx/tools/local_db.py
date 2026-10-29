"""
local_db.py - constrói uma base DuckDB local que replica o catálogo Databricks
(bronze/silver/gold/ref) executando OS MESMOS ficheiros sql/*.sql traduzidos.

Usado por:
  * tests/test_parity.py      (dados reais extraídos do .pbix)
  * tools/build_demo_db.py    (dados sintéticos de sample_data/ para o modo DEMO da app)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.sqlkit import SQL_DIR, render, split_statements, to_duckdb

PIPELINE_SQL_FILES = [
    "01_reference_data.sql",
    "20_silver_pipeline.sql",
    "21_silver_other.sql",
    "30_gold_views.sql",
]


def build(db_path: Path, bronze: dict[str, pd.DataFrame], rls_raw: pd.DataFrame,
          as_of_date: str | None = None, catalog: str | None = None,
          leads_source_active: str = "DEV"):
    import duckdb

    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    catalog = catalog or db_path.stem          # em DuckDB o "catálogo" = nome do ficheiro
    con = duckdb.connect(str(db_path))
    for schema in ("bronze", "silver", "gold", "ref"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

    for name, df in bronze.items():
        df = df.copy()
        df["_ingested_at"] = pd.Timestamp.now()
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {catalog}.bronze.{name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    con.register("tmp_df", rls_raw)
    con.execute(f"CREATE OR REPLACE TABLE {catalog}.ref.rls_user_access_raw AS SELECT * FROM tmp_df")
    con.unregister("tmp_df")

    params = {"catalog": catalog, "admin_group": "crm_report_admins",
              "leads_source_active": leads_source_active}
    for f in PIPELINE_SQL_FILES:
        sql = to_duckdb(render((SQL_DIR / f).read_text(encoding="utf-8"), params), as_of_date)
        for stmt in split_statements(sql):
            try:
                con.execute(stmt)
            except Exception as exc:  # pragma: no cover - ajuda a depurar
                raise RuntimeError(f"Erro em {f}:\n{stmt[:600]}\n\n{exc}") from exc
    return con, catalog
