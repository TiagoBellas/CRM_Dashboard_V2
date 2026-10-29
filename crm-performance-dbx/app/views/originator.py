"""Leads by Originator (página 'Leads by Originator')."""
import plotly.express as px
import streamlit as st

from crm_app import charts, context, metrics as m, ui

ui.header("Leads by Originator", "Registos por originador e segmento")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()
c1, c2 = st.columns([2, 1])
plats = sorted(df["platform"].dropna().unique())
sel = c1.multiselect("Platform (filtro desta página)", plats, placeholder="Todas", key="ob_plat")
years = sorted(df["created_on"].dt.year.dropna().astype(int).unique().tolist())
year = c2.selectbox("Leads added in", ["Todos"] + years, key="ob_year")
d = df[df["platform"].isin(sel)] if sel else df
d = d if year == "Todos" else d[d["created_on"].dt.year == year]
if ui.empty_guard(d):
    st.stop()
ui.kpi_row([("Records", f"{d['record_id'].nunique():,}", m.fmt_eur_short(d["amount_eur"].sum()))])
g = m.by_dim_and_segment(d, "originator", "count")
top = g.groupby("originator", observed=True)["value"].sum().sort_values(ascending=False).head(25).index
g = g[g["originator"].isin(top)]
g["originator"] = g["originator"].astype(str)
a, b = st.columns([2, 1])
fig = px.bar(g, y="originator", x="value", color="segment", orientation="h",
             color_discrete_map=charts.SEG_COLOR_MAP, title="Records by Originator (top 25)",
             category_orders={"originator": list(top), "segment": [s for s, _, _ in m.SEGMENTS]})
fig.update_layout(height=620, yaxis_title=None, xaxis_title=None, legend_title=None)
a.plotly_chart(fig, width="stretch")
b.plotly_chart(charts.donut_segments(d), width="stretch")
st.markdown("#### CRM Record list")
ui.records_table(d[d["active_stage"].str.upper() != "LOST"], key="originator_records")
