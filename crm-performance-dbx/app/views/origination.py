"""Origination = páginas 'Lead Origination by Platform & Country' e 'Leads Segment by Country'."""
import streamlit as st

from crm_app import charts, context, metrics as m, ui

ui.header("Lead Origination", "Distribuição por segmento (100%) por plataforma ou país")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()
c1, c2, c3 = st.columns(3)
dim_lbl = c1.segmented_control("Agrupar por", ["Platform", "Country"], default="Platform", key="or_dim")
val_lbl = c2.segmented_control("Medida", ["Quantidade", "Montante (€)"], default="Quantidade", key="or_val")
years = sorted(df["created_on"].dt.year.dropna().astype(int).unique().tolist())
year = c3.selectbox("Leads | Deals added in", ["Todos"] + years, index=0, key="or_year")
dim = "platform" if dim_lbl == "Platform" else "country_name"
value = "amount" if val_lbl == "Montante (€)" else "count"
d = df if year == "Todos" else df[df["created_on"].dt.year == year]

ui.kpi_row([(f"Records in {year}", f"{m.fmt_eur_short(d['amount_eur'].sum())}",
             f"{d['record_id'].nunique():,} registos")])
st.plotly_chart(charts.stacked_100(m.by_dim_and_segment(d, dim, value), dim, value), width="stretch")
st.markdown("#### CRM Record list")
ui.records_table(d[d["active_stage"].str.upper() != "LOST"], key="origination_records")
