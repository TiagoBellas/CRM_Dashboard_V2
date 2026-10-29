"""
build_demo_db.py - constrói sample_data/crm_reporting_demo.duckdb a partir dos CSV
sintéticos, executando os MESMOS ficheiros sql/*.sql do projeto (traduzidos para DuckDB).
Uso:
    python tools/generate_sample_data.py
    python tools/build_demo_db.py
    cd app && APP_BACKEND=duckdb streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from crm_etl.rls import read_raw, transform  # noqa: E402
from tools.local_db import build  # noqa: E402

S = ROOT / "sample_data"
DATES = {
    "crm_deal_pipeline": ["CreatedOn", "ModifiedOn", "ClosedOn", "PassedToNBO", "PassedToDD", "PassedToIC", "PassedToWon"],
    "crm_leads": ["CreatedOn", "ModifiedOn", "ClosedOn"],
    "crm_user_access_platform": ["MonthStart", "LastAccessInMonthUtc"],
}


def main(leads_source_active: str = "DEV") -> Path:
    bronze = {}
    for name in ["crm_deal_pipeline", "investment_allocation", "crm_user_access_platform", "crm_all_users", "crm_leads"]:
        df = pd.read_csv(S / f"{name}.csv", parse_dates=DATES.get(name, []),
                         dtype={"LastLogin": str} if name == "crm_all_users" else None)
        bronze[name] = df
    rls = transform(read_raw(str(S / "rls" / "UserPlatformCountry.csv")))
    con, cat = build(S / "crm_reporting_demo.duckdb", bronze, rls, leads_source_active=leads_source_active)
    n = con.execute(f"SELECT COUNT(*) FROM {cat}.gold.vw_pipeline").fetchone()[0]
    con.close()
    print(f"Base demo criada: {S / 'crm_reporting_demo.duckdb'}  (gold.vw_pipeline = {n} linhas)")
    return S / "crm_reporting_demo.duckdb"


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "DEV")
