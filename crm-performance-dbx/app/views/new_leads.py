"""New Leads by Segment = páginas 'New Leads by Segment' e 'New Leads by Segment 2' (últimos 13 meses)."""
import streamlit as st

from crm_app import charts, context, metrics as m, ui

ui.header("New Leads by Segment", "Registos criados por mês e segmento (últimos 13 meses) + acumulado no ano")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()
mode = st.segmented_control("Gráfico", ["Barras empilhadas", "Linhas (escala log)"], default="Barras empilhadas",
                            key="nl_mode")
pv, monthly = m.monthly_by_segment(df, context.today())
if pv.empty:
    st.info("Sem registos nos últimos 13 meses.")
    st.stop()
st.plotly_chart(charts.monthly_lines(pv, monthly, "bars" if mode.startswith("Barras") else "lines"),
                width="stretch")
tbl = pv.copy()
tbl.columns = [f"{c:%b %Y}" for c in tbl.columns]
tbl.loc["Total"] = tbl.sum()
tbl.loc["Cumulative YTD"] = monthly.set_index("month_start")["cumulative_ytd"].reindex(pv.columns).values
tbl.loc["Monthly contribution %"] = [m.fmt_pct(v, 0) for v in
                                     monthly.set_index("month_start")["monthly_contribution"].reindex(pv.columns)]
st.dataframe(tbl.astype(str), width="stretch")
