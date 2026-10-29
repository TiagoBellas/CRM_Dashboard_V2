"""Componentes de interface partilhados por todas as páginas."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from crm_app import metrics as m

PRIMARY = "#0f617d"

CSS = f"""
<style>
.block-container {{padding-top: 1.6rem; padding-bottom: 2rem;}}
.crm-header {{display:flex; justify-content:space-between; align-items:flex-end;
  border-bottom: 3px solid {PRIMARY}; padding-bottom: .4rem; margin-bottom: 1rem;}}
.crm-header h1 {{font-size: 1.55rem; margin: 0; color: {PRIMARY};}}
.crm-header .sub {{font-size: .85rem; color: #5d6d7e;}}
.crm-kpi {{background: #f3f6f8; border-left: 4px solid {PRIMARY}; border-radius: 6px;
  padding: .55rem .8rem; height: 100%;}}
.crm-kpi .lbl {{font-size: .75rem; text-transform: uppercase; color: #5d6d7e; letter-spacing: .03em;}}
.crm-kpi .val {{font-size: 1.45rem; font-weight: 700; color: #1f4964; line-height: 1.25;}}
.crm-kpi .hint {{font-size: .72rem; color: #7b8a97;}}
.crm-note {{font-size: .8rem; color: #5d6d7e; background:#fbf7e6; border-radius:4px; padding:.35rem .6rem;}}
@media (prefers-color-scheme: dark) {{
  .crm-kpi {{background: #1e2a33;}} .crm-kpi .val {{color: #e6eef3;}}
  .crm-header h1 {{color: #76d5ff;}} .crm-note {{background:#3a3520; color:#e9e3c7;}}
}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    refresh = st.session_state.get("last_refresh")
    ref_txt = f"Last Refresh: {refresh:%d/%m/%Y %H:%M}" if refresh is not None and pd.notna(refresh) else ""
    st.markdown(
        f"<div class='crm-header'><div><div class='sub'>DMS REPORTING</div><h1>{title}</h1>"
        f"<div class='sub'>{subtitle}</div></div><div class='sub'>{ref_txt}</div></div>",
        unsafe_allow_html=True)


def kpi_row(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, hint) in zip(cols, items):
        col.markdown(f"<div class='crm-kpi'><div class='lbl'>{label}</div><div class='val'>{value}</div>"
                     f"<div class='hint'>{hint}</div></div>", unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f"<div class='crm-note'>{text}</div>", unsafe_allow_html=True)


def empty_guard(df: pd.DataFrame) -> bool:
    if df.empty:
        st.info("Não existem registos para os filtros selecionados (ou para os seus acessos).")
        return True
    return False


RECORD_COLUMNS = {
    "record_name": "Name", "record_type": "Record Type", "platform": "Platform", "segment": "Segment",
    "vertical": "Vertical", "country_name": "Country", "originator": "Originator", "seller": "Seller",
    "owner_name": "Owner", "stage_snapshot": "Stage", "terminal_snapshot": "Status",
    "lead_status": "Lead Status", "last_deal_status": "Last Deal Status", "closure_reason": "Closure Reason",
    "created_on": "Created On", "closed_on": "Closed On", "amount_eur": "Amount (€)",
    "average_deal_age_days": "Deal Age (days)", "time_in_stage": "Time in Stage",
    "crm_record_url": "CRM",
}


def records_table(df: pd.DataFrame, key: str, height: int = 420, extra_cols: list[str] | None = None) -> None:
    """Tabela "Deals" do PBI (CRM Record list) com link para o registo no CRM e exportação."""
    cols = [c for c in RECORD_COLUMNS if c in df.columns] + [c for c in (extra_cols or []) if c in df.columns]
    t = df[cols].sort_values("amount_eur", ascending=False, na_position="last").rename(columns=RECORD_COLUMNS)
    st.dataframe(
        t, hide_index=True, width="stretch", height=height, key=key,
        column_config={
            "CRM": st.column_config.LinkColumn("CRM", display_text="abrir"),
            "Amount (€)": st.column_config.NumberColumn(format="€ %,.0f"),
            "Created On": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Closed On": st.column_config.DateColumn(format="DD/MM/YYYY"),
        })
    c1, c2 = st.columns([1, 4])
    c1.download_button("Exportar CSV", t.to_csv(index=False).encode("utf-8"), file_name=f"{key}.csv",
                       mime="text/csv", key=f"dl_{key}")
    c2.caption(f"{len(t):,} registos · {m.fmt_eur_short(df['amount_eur'].sum())}")
