"""Configuração da app (lida de variáveis de ambiente definidas em app.yaml)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    backend: str            # "databricks" (produção) ou "duckdb" (demo local)
    auth_mode: str          # "obo" (user authorization - recomendado) ou "sp" (service principal)
    catalog: str            # catálogo Unity Catalog do ambiente
    warehouse_id: str | None
    demo_db_path: str
    cache_ttl_seconds: int
    app_title: str

    @property
    def is_demo(self) -> bool:
        return self.backend == "duckdb"


def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[2]
    return Settings(
        backend=os.getenv("APP_BACKEND", "databricks").lower(),
        auth_mode=os.getenv("AUTH_MODE", "obo").lower(),
        catalog=os.getenv("CRM_CATALOG", "crm_reporting_dev"),
        warehouse_id=os.getenv("DATABRICKS_WAREHOUSE_ID"),
        demo_db_path=os.getenv("DEMO_DB_PATH", str(root / "sample_data" / "crm_reporting_demo.duckdb")),
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "600")),
        app_title=os.getenv("APP_TITLE", "DMS Reporting - CRM Performance"),
    )
