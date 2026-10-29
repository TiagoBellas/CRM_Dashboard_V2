"""Pipeline Matrix = páginas 'Lead & Deal Overview' e 'Platform Deals Summary Table'."""
import pandas as pd
import streamlit as st

from crm_app import context, metrics as m, ui

ui.header("Pipeline Matrix", "Valor do pipeline por stage atual (ActiveStage), excluindo 'Lost'")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()
c1, c2 = st.columns(2)
view = c1.segmented_control("Linhas", ["Segment", "Platform x Segment"], default="Segment", key="mx_rows")
value = c2.segmented_control("Valores", ["Montante (€)", "Quantidade"], default="Montante (€)", key="mx_val")
rows = ["segment"] if view == "Segment" else ["platform", "segment"]
val = "count" if value == "Quantidade" else "amount"

amt = m.stage_matrix(df, rows, "amount")
cnt = m.stage_matrix(df, rows, "count")
if val == "amount":
    show = amt.copy().astype(object)
    for c in amt.columns:
        show[c] = [f"{m.fmt_eur_short(a)} ({int(n)})" if a or n else "--"
                   for a, n in zip(amt[c], cnt.reindex(amt.index)[c].fillna(0))]
else:
    show = cnt.astype(int)
show = show.reset_index().rename(columns={"segment": "Segment", "platform": "Platform"})
st.dataframe(show, hide_index=True, width="stretch", height=min(60 + 36 * len(show), 700))
st.caption("Célula = soma de Amount (€) e, entre parênteses, nº de registos (medida '0. Pipeline Matrix Cell').")

st.markdown("#### CRM Record list")
ui.records_table(df[df["active_stage"].str.upper() != "LOST"], key="matrix_records")
