"""Testes unitários das medidas (app/crm_app/metrics.py) com dados mínimos e resultados conhecidos."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from crm_app import metrics as m  # noqa: E402


def _df():
    rows = [
        # id, type, active, lead_status, state, reached, lost_amt_idx, lost_cnt_idx, amount, created, closed, country
        ("A", "Lead", "Lead", "Early Lead", "Active", 1, None, None, 10.0, "2026-01-10", None, "Portugal"),
        ("B", "Lead", "Lead", "Rejected", "Active", 1, 1, 1, 20.0, "2026-04-05", "2026-05-01", "Portugal"),
        ("C", "Deal", "Early Prospect", None, "Active", 2, None, None, 30.0, "2026-04-20", None, "Italy"),
        ("D", "Deal", "Lost", None, "Lost", 3, 3, 3, 40.0, "2025-04-15", "2026-02-01", "Italy"),
        ("E", "Deal", "Won", None, "Won", 7, None, None, 50.0, "2025-07-01", "2026-03-01", "Spain"),
        ("F", "Deal", "In Due Diligence", None, "Active", 4, None, None, None, "2026-07-02", None, "Spain"),
    ]
    df = pd.DataFrame(rows, columns=["record_id", "record_type", "active_stage", "lead_status", "state_name",
                                     "funnel_reached_stage_index", "funnel_lost_stage_index_amount",
                                     "funnel_lost_stage_index_count", "amount_eur", "created_on", "closed_on",
                                     "country_name"])
    df["record_key"] = df["record_id"]
    df["status_name"] = df["state_name"]
    for c in ("created_on", "closed_on"):
        df[c] = pd.to_datetime(df[c])
    df["quarter_start"] = df["created_on"].dt.to_period("Q").dt.start_time
    df["segment"] = "Other"
    df["platform"] = "P1"
    for c in ("passed_to_nbo", "passed_to_dd", "passed_to_ic", "passed_to_won"):
        df[c] = pd.NaT
    return df


def test_formatting():
    assert m.fmt_eur_short(1_234_567) == "€ 1.2M"
    assert m.fmt_eur_short(3_450_000_000) == "€ 3.45B"
    assert m.fmt_eur_short(12_000) == "€ 12.0K"
    assert m.fmt_pct(0.1234) == "12.3%"
    assert m.safe_div(1, 0) is None


def test_funnel_is_cumulative():
    f = m.funnel(_df()).set_index("stage_index")
    assert f.loc[1, "active_count"] == 6          # todos alcançaram Lead
    assert f.loc[2, "active_count"] == 4          # C, D, E, F
    assert f.loc[4, "active_count"] == 2          # F (4) e E (7)
    assert f.loc[7, "active_count"] == 1
    assert f.loc[1, "active_amount"] == 150.0     # F sem montante conta 0
    assert f.loc[3, "lost_amount"] == 40.0 and f.loc[1, "lost_count"] == 1


def test_kpis():
    ia = pd.DataFrame({"year": [2026, 2026, 2025], "country_name": ["Spain", "France", "Spain"],
                       "budget_base": [100.0, 999.0, 7.0]})
    k = m.kpis(_df(), ia, today=date(2026, 10, 1))
    assert k["total_items"] == 6 and k["win_count"] == 1
    assert k["lost_deals"] == 2                   # 1 Lost + 1 Rejected
    assert abs(k["lose_rate"] - 2 / 6) < 1e-9
    assert k["pp_budget"] == 100.0                # só países presentes no pipeline e ano atual
    assert k["pp_achievement"] == 0.5             # Won fechado em 2026 = 50 / 100


def test_quarter_comparison():
    c = m.quarter_comparison(_df(), pd.Timestamp("2026-04-01"), "DEAL", "count")
    assert (c["current"], c["previous"], c["ly"]) == (1, 0, 1)   # C ; - ; D
    assert c["yoy_pct"] == 0 and c["qoq_pct"] is None
    assert c["share"] == 0.5                                     # 1 deal vs 1 lead (B) em Q2-2026
    assert m.quarter_label(pd.Timestamp("2026-10-01")) == "Q4-2026"


def test_stage_matrix_excludes_lost():
    mx = m.stage_matrix(_df(), ["segment"], "count")
    assert "0. Lost" not in mx.columns
    assert mx.loc["Total", "Total"] == 5
