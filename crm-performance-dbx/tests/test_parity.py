"""
Teste de PARIDADE  Power BI  x  SQL do projeto.

1. Reconstrói a camada bronze a partir da tabela "Pipeline" extraída do .pbix
   (desfazendo as renomeações do Power Query).
2. Executa os MESMOS ficheiros sql/*.sql (traduzidos para DuckDB).
3. Compara, linha a linha, cada coluna calculada DAX com a coluna SQL equivalente.

Pré-requisito:  python tools/extract_pbix_reference.py <ficheiro.pbix>
Execução:       pytest -q tests/test_parity.py        (ou: python tests/test_parity.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PARITY = ROOT / ".parity"
AS_OF = "2026-10-23"  # data do último refresh do .pbix (tabela LastRefresh)

# coluna DAX  ->  coluna SQL
COLUMN_MAP = {
    "Stage Snapshot": "stage_snapshot",
    "Stage Snapshot Index": "stage_snapshot_index",
    "Terminal Snapshot": "terminal_snapshot",
    "Terminal Snapshot v2": "terminal_snapshot_v2",
    "Terminal Snapshot 2": "terminal_snapshot_2",
    "Decomp Closure Reason": "decomp_closure_reason",
    "CRM Record URL": "crm_record_url",
    "Month Year": "month_year",
    "Quarter Year": "quarter_year",
    "Quarter Label": "quarter_label",
    "Quarter Number": "quarter_number",
    "Quarter Sort": "quarter_sort",
    "Quarter Start": "quarter_start",
    "Month Start": "month_start",
    "Pipeline Created Month Start": "month_start",
    "DQ Expected Terminal": "dq_expected_terminal",
    "DQ Expected Stage Name": "dq_expected_stage_name",
    "DQ Expected Stage Snapshot": "dq_expected_stage_snapshot",
    "DQ Lead Rejected Issue": "dq_lead_rejected_issue",
    "DQ Deal Lost Issue": "dq_deal_lost_issue",
    "DQ Stage Classification Issue": "dq_stage_classification_issue",
    "DQ Source State Conflict": "dq_source_state_conflict",
    "DQ Has Classification Issue": "dq_has_classification_issue",
    "DQ Primary Issue": "dq_primary_issue",
    "DQ Severity": "dq_severity",
    "DQ Issue Description": "dq_issue_description",
    "DQ Amount": "dq_amount",
    "RLS Match Platform": "rls_match_platform",
    "RLS Match Country": "rls_match_country",
    "Stage Age Days (Snapshot)": "stage_age_days_snapshot",
    "Time in Stage": "time_in_stage",
    "Average Deal Age Column": "average_deal_age_days",
    "Show Row - Closed This Year Or Blank": "show_row_closed_this_year_or_blank",
    # colunas do Power Query
    "Segment": "segment",
    "Platform": "platform",
    "Vertical": "vertical",
    "Central MD": "central_md",
    "Originator": "originator",
    "ActiveStage": "active_stage",
    "LastDealStatus": "last_deal_status",
}

needs_reference = pytest.mark.skipif(
    not (PARITY / "Pipeline.parquet").exists(),
    reason="Sem dados de referência (.parity/). Corra tools/extract_pbix_reference.py",
)


def _bronze_from_reference() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    p = pd.read_parquet(PARITY / "Pipeline.parquet")
    calc_cols = [c for c in COLUMN_MAP if c not in
                 ("Segment", "Platform", "Vertical", "Central MD", "Originator", "ActiveStage", "LastDealStatus")]
    keep = [c for c in p.columns if c not in calc_cols and c not in ("RLS Match Scope",)]
    b = p[keep].rename(columns={"Vertical": "Template", "Central MD": "CentralMD", "Originator": "OriginatorName"})
    # o PQ extrai o texto após o último " - "; simulamos o valor original da fonte
    b["Segment"] = "Strategy - " + b["Segment"].astype("string")
    b = b.astype({c: "object" for c in b.columns if str(b[c].dtype).startswith("string")})

    ia = pd.read_parquet(PARITY / "Investment_Allocation.parquet")
    leads = pd.read_parquet(PARITY / "Leads.parquet").rename(columns={
        "Amount (€)": "AmountInEuro"})
    leads["_source_env"] = "DEV"   # no PBI os Leads vinham da base DEV (achado A1)
    uap = pd.read_parquet(PARITY / "User_Access_Platform.parquet").drop(columns=["Year", "Month", "MonthNumber"])
    users = pd.read_parquet(PARITY / "User_Access.parquet").drop(columns=["LastLoginRange"])
    users["ActiveCRMUser"] = "Yes"
    rls = pd.read_parquet(PARITY / "RLS_UserAccess_Raw.parquet").rename(columns={
        "(Do Not Modify) User": "user_id", " Full Name": "full_name", "Platform": "platform",
        "Country": "country", "Primary Email": "primary_email"})
    rls = rls[["user_id", "full_name", "platform", "country", "primary_email"]]
    to_obj = lambda d: d.astype({c: "object" for c in d.columns if str(d[c].dtype).startswith("string")})
    bronze = {
        "crm_deal_pipeline": b,
        "investment_allocation": to_obj(ia),
        "crm_leads": to_obj(leads),
        "crm_user_access_platform": to_obj(uap),
        "crm_all_users": to_obj(users),
    }
    return bronze, to_obj(rls)


def _norm(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.strftime("%Y-%m-%d").fillna("<NULL>")
    def f(v):
        if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
            return "<NULL>"
        if isinstance(v, (bool,)):
            return str(int(v))
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if str(v) == "":
            return "<NULL>"           # DAX não distingue "" de BLANK
        return str(v)
    return s.astype(object).map(f)


def run_parity(verbose: bool = True) -> dict[str, int]:
    from tools.local_db import build

    bronze, rls = _bronze_from_reference()
    con, cat = build(ROOT / ".parity" / "parity.duckdb", bronze, rls, as_of_date=AS_OF)
    sql = con.execute(f"SELECT * FROM {cat}.gold.vw_pipeline_all").df()
    ref = pd.read_parquet(PARITY / "Pipeline.parquet")
    m = ref.merge(sql, left_on="RecordId", right_on="record_id", how="left", suffixes=("", "_sql"))
    assert len(m) == len(ref) and m["record_id"].notna().all()

    diffs = {}
    for dax, col in COLUMN_MAP.items():
        a, b = _norm(m[dax]), _norm(m[col])
        bad = (a != b)
        diffs[dax] = int(bad.sum())
        if verbose:
            status = "OK " if bad.sum() == 0 else "DIF"
            print(f"[{status}] {dax:38s} -> {col:35s} diferenças: {bad.sum()}")
            if bad.sum():
                ex = m.loc[bad, [dax, col]].head(3)
                print("       exemplos:", ex.to_dict("records"))

    # ---- RLS: as colunas da tabela de acessos
    r_ref = pd.read_parquet(PARITY / "RLS_UserAccess_Raw.parquet")
    r_sql = con.execute(f"SELECT * FROM {cat}.silver.rls_user_access").df()
    for dax, col in [("RLS Email", "rls_email"), ("RLS Match Platform", "rls_match_platform"),
                     ("RLS Country Token", "rls_country_token"), ("RLS Access Type", "rls_access_type")]:
        a = sorted(_norm(r_ref[dax]).tolist())
        b = sorted(_norm(r_sql[col]).tolist())
        n = sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))
        diffs["RLS::" + dax] = n
        if verbose:
            print(f"[{'OK ' if n == 0 else 'DIF'}] RLS {dax:34s} -> {col:35s} diferenças: {n}")

    # ---- RLS: visibilidade por utilizador (regra DAX em pandas vs SQL)
    pairs = con.execute(f"SELECT rls_email, record_id FROM {cat}.silver.pipeline_user_access").df()
    glob = set(r_sql.loc[r_sql.rls_access_type == "GLOBAL", "rls_email"])
    mismatched_users = 0
    for email, grp in r_ref.groupby("RLS Email"):
        rows = r_ref[r_ref["RLS Email"] == email]
        vis = pd.Series(False, index=ref.index)
        for _, r in rows.iterrows():
            t = r["RLS Access Type"]
            if t == "GLOBAL":
                vis[:] = True
            elif t == "COUNTRY_ALL":
                vis |= ref["RLS Match Country"].fillna("") == "PORTUGAL"
            else:
                tok = r["RLS Country Token"] or ""
                vis |= (ref["RLS Match Platform"] == r["RLS Match Platform"]) & ref["RLS Match Country"].notna() & \
                       ref["RLS Match Country"].fillna("#").map(lambda c: f"|{c}|" in tok)
        dax_ids = set(ref.loc[vis.fillna(False), "RecordId"])
        sql_ids = set(ref["RecordId"]) if email in glob else set(pairs.loc[pairs.rls_email == email, "record_id"])
        mismatched_users += int(dax_ids != sql_ids)
    diffs["RLS::visibilidade por utilizador"] = mismatched_users
    if verbose:
        print(f"[{'OK ' if mismatched_users == 0 else 'DIF'}] RLS visibilidade: utilizadores com resultado diferente = {mismatched_users}")
    con.close()
    return diffs


@needs_reference
def test_parity_all_columns():
    diffs = run_parity(verbose=True)
    failing = {k: v for k, v in diffs.items() if v}
    assert not failing, f"Colunas com diferenças: {failing}"


if __name__ == "__main__":
    run_parity(verbose=True)
