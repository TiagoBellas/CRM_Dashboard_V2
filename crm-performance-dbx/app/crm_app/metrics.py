"""
metrics.py - as MEDIDAS DAX do Power BI reescritas como funções pandas puras.

Cada função recebe o DataFrame do pipeline JÁ FILTRADO (equivalente ao contexto de
filtro / ALLSELECTED do DAX) e devolve números ou tabelas prontas para os gráficos.
Não há aqui nada de Streamlit -> tudo é testável em tests/test_metrics.py.
A correspondência medida DAX -> função está em docs/02_Mapeamento_DAX_SQL.md.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constantes (ref.dim_stage / ref.dim_segment)
# --------------------------------------------------------------------------- #
STAGES = {0: "Lost", 1: "Lead", 2: "Early Prospect", 3: "NBO / Preliminary Bids",
          4: "In Due Diligence", 5: "IC Approved", 6: "Won, Closing", 7: "Won"}
STAGE_DISPLAY = {i: f"{i}. {n}" for i, n in STAGES.items()}
STAGE_BY_UPPER = {n.upper(): i for i, n in STAGES.items()}
STAGE_COLORS = {1: "#004c6d", 2: "#006b9b", 3: "#0092d1", 4: "#37b3e5",
                5: "#76d5ff", 6: "#9b6bb5", 7: "#94A3B8"}
SEGMENTS = [  # (nome, abreviado, ordem)
    ("Real Estate Lending", "RE Lending", 1), ("Opportunistic Credit", "Opp. Credit", 2),
    ("Non-Performing", "NPL", 3), ("Bankruptcies and restructuring", "B&R", 4),
    ("Single Name Credits", "SN Credit", 5), ("Secured Collaterals & Value-add", "Secured Coll. & VA", 6),
    ("Real-estate Equity", "RE Equity", 7), ("Investment Grade Asset-Backed", "IG Asset-Backed", 8),
    ("Other", "Other", 9)]
SEGMENT_ORDER = {s: i for s, _, i in SEGMENTS}
SEGMENT_COLORS = ["#004c6d", "#0092d1", "#76d5ff", "#9b6bb5", "#33AE81", "#F3C911",
                  "#DD915F", "#DC5B57", "#94A3B8"]


# --------------------------------------------------------------------------- #
# Formatação (medidas "Deal Amount", "Pipeline Count Label", etc.)
# --------------------------------------------------------------------------- #
def fmt_eur_short(v, space: bool = True) -> str:
    """Medida DAX [Deal Amount]: € 1.2M / € 3.45B / € 12.0K."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    sym = "€ " if space else "€"
    a = abs(v)
    if a == 0:
        return f"{sym}0"
    if a >= 1e9:
        return f"{sym}{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sym}{v / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sym}{v / 1e3:.1f}K"
    return f"{sym}{v:.0f}"


def fmt_pct(v, decimals: int = 1) -> str:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "--"
    return f"{v * 100:.{decimals}f}%"


def fmt_int(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    return f"{int(v):,}"


def safe_div(a, b):
    """DIVIDE() do DAX: devolve None quando o divisor é 0/vazio."""
    try:
        if b is None or b == 0 or pd.isna(b) or a is None or pd.isna(a):
            return None
        return a / b
    except TypeError:
        return None


def _up(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.upper()


def _days(end: pd.Series, start: pd.Series) -> pd.Series:
    """DATEDIFF(start, end, DAY) do DAX = diferença entre datas de calendário."""
    return (pd.to_datetime(end).dt.normalize() - pd.to_datetime(start).dt.normalize()).dt.days


def _amount_per_record(df: pd.DataFrame) -> pd.Series:
    """SUMX(VALUES(RecordId), MAX(AmountInEuro)) - evita contar valores duplicados."""
    d = df[df["record_id"].notna()]
    return d.groupby("record_id")["amount_eur"].max().fillna(0)


# --------------------------------------------------------------------------- #
# KPIs gerais (Pipeline: Win Rate, Lose Rate %, Average Deal Size, PP Budget ...)
# --------------------------------------------------------------------------- #
def kpis(df: pd.DataFrame, investment: pd.DataFrame | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    total = int(df["record_id"].notna().sum())
    active_up = _up(df["active_stage"])
    lead_up = _up(df["lead_status"])
    win_count = int((active_up == "WON").sum())
    lost = int((active_up == "LOST").sum() + (lead_up == "REJECTED").sum())
    won_mask = (active_up == "WON")
    won_cy = df.loc[won_mask & (df["closed_on"].dt.year == today.year), "amount_eur"].sum()

    budget = None
    if investment is not None and not investment.empty:
        countries = set(df["country_name"].dropna())
        ia = investment[(investment["year"] == today.year) & (investment["country_name"].isin(countries))]
        budget = float(ia["budget_base"].sum()) if not ia.empty else None

    return {
        "total_items": total,                                         # [Total Pipeline Items]
        "win_count": win_count,                                       # [Win Count]
        "win_rate": safe_div(win_count, total),                       # [Win Rate] ("Conversion Rate %")
        "lost_deals": lost,                                           # [Lost Deals]
        "lose_rate": safe_div(lost, total),                           # [Lose Rate %]
        "open_deals": int(df.loc[(active_up != "LOST") & (lead_up.fillna("") != "REJECTED"), "record_id"].nunique()),
        "total_amount": float(df["amount_eur"].sum()),                # [Pipeline Value Raw]
        "non_lost_pipeline": float(df.loc[(active_up != "LOST") & (lead_up.fillna("") != "REJECTED"), "amount_eur"].sum()),
        "won_amount": float(df.loc[won_mask, "amount_eur"].sum()),    # [Won Amount]
        "avg_deal_size": safe_div(df["amount_eur"].sum(), df["record_id"].nunique()),  # [Average Deal Size]
        "avg_deal_age_won": avg_deal_age_won(df, today),              # [Average Deal Age (Won only)]
        "pp_budget": budget,                                          # [PP 2026 Budget]
        "pp_achievement": safe_div(won_cy, budget),                   # [% Achievement vs 2026 PP]
    }


def avg_deal_age(df: pd.DataFrame, today: date | None = None) -> float | None:
    """[Average Deal Age]: média (em dias) de CreatedOn -> ClosedOn (ou hoje), ignora negativos."""
    if df.empty:
        return None
    today_ts = pd.Timestamp(today or date.today())
    end = df["closed_on"].fillna(today_ts)
    d = _days(end, df["created_on"])
    d = d[d.notna() & (d >= 0)]
    return None if d.empty else float(round(d.mean()))


def avg_deal_age_won(df: pd.DataFrame, today: date | None = None) -> float | None:
    st_ = _up(df["state_name"]); ac = _up(df["active_stage"]); su = _up(df["status_name"])
    won = (st_ == "WON") | ac.isin(["WON", "CLOSED"]) | (su == "WON")
    return avg_deal_age(df[won.fillna(False) & df["closed_on"].notna()], today)


def fmt_days(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    v = int(round(v))
    return f"{v} day" if v == 1 else f"{v} days"


# --------------------------------------------------------------------------- #
# Funil (medidas "1. Active Amount €", "Lost Amount (At Stage) €", "1. Active", ...)
# --------------------------------------------------------------------------- #
def funnel(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por stage 1..7 com valores ativos (alcançaram o stage) e perdidos no stage."""
    amounts = _amount_per_record(df)
    total_amount = float(amounts.sum())
    total_count = int(df["record_id"].notna().sum())                   # [1. Funnel Total]
    rows = []
    for idx in range(1, 8):
        reached = df[df["funnel_reached_stage_index"] >= idx]
        rid = reached["record_id"].dropna().unique()
        active_amt = float(amounts.reindex(rid).fillna(0).sum())
        active_cnt = int(reached["record_key"].nunique())
        lost_amt = lost_cnt = None
        if idx <= 5:
            lost_a = df[df["funnel_lost_stage_index_amount"] == idx]["record_id"].dropna().unique()
            lost_amt = float(amounts.reindex(lost_a).fillna(0).sum())
            lost_cnt = int(df.loc[df["funnel_lost_stage_index_count"] == idx, "record_id"].nunique())
        rows.append({
            "stage_index": idx, "stage_name": STAGES[idx],
            "active_count": active_cnt,                                  # [1. Active]
            "active_amount": active_amt,                                 # [1. Active Amount €]
            "pct_amount": safe_div(active_amt, total_amount),
            "pct_count": safe_div(active_cnt, total_count),              # [Percentage at Stage Count]
            "lost_amount": lost_amt,                                     # [Lost Amount (At Stage) €]
            "pct_lost_amount": safe_div(lost_amt, total_amount) if lost_amt is not None else None,
            "lost_count": lost_cnt,                                      # [Lost Deals Count]
        })
    out = pd.DataFrame(rows)
    nxt = out["active_count"].shift(-1)
    out["conversion_to_next"] = [safe_div(n, c) for n, c in zip(nxt, out["active_count"])]
    out.attrs["total_amount"] = total_amount
    out.attrs["total_count"] = total_count
    return out


def avg_days_in_stage(df: pd.DataFrame, leads: pd.DataFrame | None, today: date | None = None) -> dict:
    """Medida [Avg Days In Stage] para cada stage."""
    def avg(start, end):
        m = df[start].notna() & df[end].notna()
        d = _days(df.loc[m, end], df.loc[m, start])
        return None if d.empty else float(d.mean())

    lead_avg = None
    if leads is not None and not leads.empty:
        l = leads[leads["closed_on"].notna() & (_up(leads["lead_status"]) == "APPROVED")]
        d = _days(l["closed_on"], l["created_on"])
        lead_avg = None if d.empty else float(d.mean())
    return {
        "Lead": lead_avg,
        "Early Prospect": avg("created_on", "passed_to_nbo"),
        "NBO / Preliminary Bids": avg("passed_to_nbo", "passed_to_dd"),
        "In Due Diligence": avg("passed_to_dd", "passed_to_ic"),
        "IC Approved": avg("passed_to_ic", "passed_to_won"),
        "Won, Closing": avg("passed_to_won", "closed_on"),
        "Won": avg_deal_age(df, today),
    }


# --------------------------------------------------------------------------- #
# Quarter Performance (tabelas _QuarterSelector / _QuarterComparison + medidas Q.)
# --------------------------------------------------------------------------- #
def quarter_label(q: pd.Timestamp) -> str:
    q = pd.Timestamp(q)
    return f"Q{(q.month - 1) // 3 + 1}-{q.year}"


def quarter_window(df_all: pd.DataFrame, today: date | None = None, months: int = 24) -> list[pd.Timestamp]:
    """Quarters disponíveis no seletor: filtro de página 'últimos 24 meses'."""
    today_ts = pd.Timestamp(today or date.today())
    lower = today_ts + pd.Timedelta(days=1) - pd.DateOffset(months=months)
    qs = pd.Series(df_all["quarter_start"].dropna().unique())
    qs = pd.to_datetime(qs)
    return sorted(q for q in qs if lower.normalize() <= q <= today_ts)


def default_selected_quarter(df_all: pd.DataFrame) -> pd.Timestamp | None:
    """[Q. Selected Quarter Start] sem seleção = quarter mais recente (REMOVEFILTERS(Pipeline))."""
    q = df_all["quarter_start"].dropna()
    return None if q.empty else pd.Timestamp(q.max())


def _q_value(df: pd.DataFrame, q: pd.Timestamp, record_type: str, measure: str) -> float:
    sub = df[(df["quarter_start"] == q) & (_up(df["record_type"]) == record_type.upper())]
    if measure == "amount":
        return float(sub["amount_eur"].sum())                            # [Q. Deals Amount]
    return float(sub["record_id"].nunique())                             # [Q. Deals Count]


def quarter_comparison(df: pd.DataFrame, selected_q: pd.Timestamp, record_type: str,
                       measure: str = "count") -> dict:
    """Cartões: Current / Previous / LY, QoQ %, YoY %, share Leads vs Deals."""
    sel = pd.Timestamp(selected_q)
    prev = sel - pd.DateOffset(months=3)
    ly = sel - pd.DateOffset(months=12)
    other = "LEAD" if record_type.upper() == "DEAL" else "DEAL"
    cur, p, l = (_q_value(df, x, record_type, measure) for x in (sel, prev, ly))
    cur_other = _q_value(df, sel, other, measure)
    return {
        "selected_label": quarter_label(sel), "previous_label": quarter_label(prev), "ly_label": quarter_label(ly),
        "current": cur, "previous": p, "ly": l,
        "qoq_change": cur - p, "qoq_pct": safe_div(cur - p, p),
        "yoy_change": cur - l, "yoy_pct": safe_div(cur - l, l),
        "share": safe_div(cur, cur + cur_other),                         # [Q. Deal Share %] / [Q. Lead Share %]
    }


def quarter_series(df: pd.DataFrame, quarters: list[pd.Timestamp], record_type: str,
                   measure: str = "count") -> pd.DataFrame:
    """Gráfico combinado: valor por quarter + QoQ % (cada quarter vs o anterior)."""
    rows = []
    for q in quarters:
        c = quarter_comparison(df, q, record_type, measure)
        rows.append({"quarter_start": q, "quarter_label": c["selected_label"],
                     "value": c["current"], "qoq_pct": c["qoq_pct"]})
    return pd.DataFrame(rows)


def quarter_pivot(df: pd.DataFrame, selected_q: pd.Timestamp, record_type: str, dim: str,
                  measure: str = "count") -> pd.DataFrame:
    """Matriz por Originator/Platform x (Selected, Previous, Same Q LY) - [Q. Deals Comparison]."""
    sel = pd.Timestamp(selected_q)
    periods = [("Selected Quarter", sel), ("Previous Quarter", sel - pd.DateOffset(months=3)),
               ("Same Quarter LY", sel - pd.DateOffset(months=12))]
    sub = df[_up(df["record_type"]) == record_type.upper()].copy()
    sub[dim] = sub[dim].fillna("(Blank)")
    cols = {}
    for name, q in periods:
        part = sub[sub["quarter_start"] == q]
        g = part.groupby(dim)["amount_eur"].sum() if measure == "amount" else part.groupby(dim)["record_id"].nunique()
        cols[f"{name} ({quarter_label(q)})"] = g
    out = pd.DataFrame(cols).fillna(0)
    out = out[(out != 0).any(axis=1)]
    out = out.sort_values(out.columns[0], ascending=False)
    if not out.empty:
        out.loc["Total"] = out.sum()
    return out


def comparison_note(df_all: pd.DataFrame, selected_q: pd.Timestamp) -> str:
    """[Q. Comparison Note]"""
    as_of = df_all["created_on"].max()
    sel = pd.Timestamp(selected_q)
    end = sel + pd.DateOffset(months=3) - pd.Timedelta(days=1)
    if pd.notna(as_of) and sel <= as_of < end:
        return (f"Selected quarter reflects data through {as_of:%d %b %Y}; "
                "Previous and LY are full quarters. No elapsed-day adjustment is applied.")
    return "All comparison periods are complete quarters."


# --------------------------------------------------------------------------- #
# Matriz Segment x Stage (Lead & Deal Overview / Platform Deals Summary)
# --------------------------------------------------------------------------- #
def stage_matrix(df: pd.DataFrame, rows: list[str], value: str = "amount") -> pd.DataFrame:
    """No PBI as colunas vêm de _DimStage ligado por ActiveStage (não Stage Snapshot);
    o stage '0. Lost' e os valores sem correspondência estão excluídos."""
    d = df.copy()
    d["_stage_idx"] = _up(d["active_stage"]).map(STAGE_BY_UPPER)
    d = d[d["_stage_idx"].notna() & (d["_stage_idx"] > 0)]
    d["_stage"] = d["_stage_idx"].astype(int).map(STAGE_DISPLAY)
    for r in rows:
        d[r] = d[r].fillna("(Blank)")
    if value == "amount":
        pv = d.pivot_table(index=rows, columns="_stage", values="amount_eur", aggfunc="sum", fill_value=0)
    else:
        pv = d.pivot_table(index=rows, columns="_stage", values="record_id", aggfunc="nunique", fill_value=0)
    pv = pv.reindex(columns=[c for c in STAGE_DISPLAY.values() if c in pv.columns])
    pv["Total"] = pv.sum(axis=1)
    if "segment" in rows and len(rows) == 1:
        pv = pv.loc[sorted(pv.index, key=lambda s: SEGMENT_ORDER.get(s, 99))]
    else:
        pv = pv.sort_values("Total", ascending=False)
    pv.loc[("Total",) * len(rows) if len(rows) > 1 else "Total", :] = pv.sum(axis=0)
    pv.columns.name = None
    return pv


# --------------------------------------------------------------------------- #
# Origination (100% stacked por Platform / Country / Originator x Segment)
# --------------------------------------------------------------------------- #
def by_dim_and_segment(df: pd.DataFrame, dim: str, value: str = "count") -> pd.DataFrame:
    d = df[df[dim].notna()]
    if value == "amount":
        g = d.groupby([dim, "segment"])["amount_eur"].sum()
    else:
        g = d.groupby([dim, "segment"])["record_id"].nunique()
    out = g.rename("value").reset_index()
    tot = out.groupby(dim)["value"].transform("sum")
    out["pct"] = out["value"] / tot.replace(0, np.nan)
    order = out.groupby(dim)["value"].sum().sort_values(ascending=False).index.tolist()
    out[dim] = pd.Categorical(out[dim], categories=order, ordered=True)
    out["segment_order"] = out["segment"].map(SEGMENT_ORDER).fillna(99)
    return out.sort_values([dim, "segment_order"])


# --------------------------------------------------------------------------- #
# New Leads by Segment (HTML "Deals Trend + Cumulative")
# --------------------------------------------------------------------------- #
def monthly_by_segment(df: pd.DataFrame, today: date | None = None, months: int = 13) -> tuple[pd.DataFrame, pd.DataFrame]:
    today_ts = pd.Timestamp(today or date.today())
    lower = (today_ts + pd.Timedelta(days=1) - pd.DateOffset(months=months)).normalize()
    d = df[(df["month_start"] >= lower) & (df["month_start"] <= today_ts)]
    pv = d.pivot_table(index="segment", columns="month_start", values="record_id", aggfunc="nunique", fill_value=0)
    pv = pv.loc[sorted(pv.index, key=lambda s: SEGMENT_ORDER.get(s, 99))] if not pv.empty else pv
    monthly = d.groupby("month_start")["record_id"].nunique().rename("added").reset_index().sort_values("month_start")
    monthly["year"] = monthly["month_start"].dt.year
    monthly["cumulative_ytd"] = monthly.groupby("year")["added"].cumsum()   # [Q. Deals Count Cumulative YTD]
    monthly["monthly_contribution"] = monthly["added"] / monthly["cumulative_ytd"]  # [0. Monthly Contribution %]
    return pv, monthly


# --------------------------------------------------------------------------- #
# DMS Usage
# --------------------------------------------------------------------------- #
def usage_latest(usage: pd.DataFrame) -> dict:
    if usage.empty:
        return {"month": None, "licensed": 0, "active": 0, "rate": None, "by_platform": pd.DataFrame()}
    latest = usage["month_key"].max()                                   # [Latest Month]
    u = usage[usage["month_key"] == latest]
    lic, act = int(u["licensed_users"].sum()), int(u["active_users"].sum())
    byp = u.groupby("platform")[["licensed_users", "active_users"]].sum()
    byp["non_accessed_users"] = byp["licensed_users"] - byp["active_users"]
    byp["login_rate"] = byp["active_users"] / byp["licensed_users"].replace(0, np.nan)
    return {"month": u["month_start"].max(), "licensed": lic, "active": act,
            "rate": safe_div(act, lic), "by_platform": byp.sort_values("licensed_users", ascending=False)}


def usage_monthly(usage: pd.DataFrame) -> pd.DataFrame:
    g = usage.groupby(["year", "month_number", "month_name"])[["licensed_users", "active_users"]].sum().reset_index()
    g["non_accessed_users"] = g["licensed_users"] - g["active_users"]
    g["login_rate"] = g["active_users"] / g["licensed_users"].replace(0, np.nan)
    return g.sort_values(["year", "month_number"])


# --------------------------------------------------------------------------- #
# Qualidade de dados (tabela DataQualityMeasures)
# --------------------------------------------------------------------------- #
def dq_summary(df: pd.DataFrame) -> dict:
    issue = df["dq_has_classification_issue"] == 1
    return {
        "affected_items": int(df.loc[issue, "record_id"].nunique()),
        "affected_leads": int(df.loc[issue & (_up(df["record_type"]) == "LEAD"), "record_id"].nunique()),
        "affected_deals": int(df.loc[issue & (_up(df["record_type"]) == "DEAL"), "record_id"].nunique()),
        "affected_amount": float(df.loc[issue, "amount_eur"].sum()),
        "critical_items": int(df.loc[issue & (df["dq_severity"] == "Critical"), "record_id"].nunique()),
        "missing_amount": int(df.loc[df["amount_eur"].isna(), "record_id"].nunique()),
        "invalid_dates": int(df.loc[df["closed_on"].notna() & df["created_on"].notna()
                                    & (df["closed_on"] < df["created_on"]), "record_id"].nunique()),
    }
