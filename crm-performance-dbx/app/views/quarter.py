"""
Quarter Performance = 4 páginas do PBI numa só:
  'Quarter Performance' (Leads Qtd), 'Leads Quarter Performance €',
  'Deals Quarter Performance Qty', 'Deals Quarter Performance €'.
Os quarters são medidos pela data de CRIAÇÃO; os filtros de data de criação são
ignorados (as medidas DAX faziam REMOVEFILTERS(Pipeline[CreatedOn])).
"""
import streamlit as st

from crm_app import charts, context, metrics as m, ui

ui.header("Quarter Performance", "Quarter selecionado vs quarter anterior vs mesmo quarter do ano anterior")
df_all = context.pipeline_all()
df = context.pipeline(ignore={"created"})
if ui.empty_guard(df_all):
    st.stop()

quarters = m.quarter_window(df_all, context.today())
default_q = m.default_selected_quarter(df_all)
if not quarters:
    quarters = [default_q]
c1, c2, c3 = st.columns([1, 1, 1])
rt = c1.segmented_control("Registos", ["Leads", "Deals"], default="Leads", key="q_rt")
meas = c2.segmented_control("Medida", ["Quantidade", "Montante (€)"], default="Quantidade", key="q_meas")
labels = [m.quarter_label(q) for q in quarters]
idx = labels.index(m.quarter_label(default_q)) if m.quarter_label(default_q) in labels else len(labels) - 1
sel_label = c3.selectbox("Quarter selecionado", labels, index=idx, key="q_sel")
sel_q = quarters[labels.index(sel_label)]
record_type = "LEAD" if rt == "Leads" else "DEAL"
measure = "amount" if meas == "Montante (€)" else "count"
fmt = m.fmt_eur_short if measure == "amount" else m.fmt_int

c = m.quarter_comparison(df, sel_q, record_type, measure)
st.caption(f"Selected: {c['selected_label']}   |   Previous: {c['previous_label']}   |   Same Q LY: {c['ly_label']}")
ui.kpi_row([
    (f"{rt} {c['selected_label']}", fmt(c["current"]), "Selected Quarter"),
    (f"{rt} {c['previous_label']}", fmt(c["previous"]), "Previous Quarter"),
    (f"{rt} {c['ly_label']}", fmt(c["ly"]), "Same Quarter LY"),
    ("QoQ %", m.fmt_pct(c["qoq_pct"]), "(Current - Previous) / Previous"),
    ("YoY %", m.fmt_pct(c["yoy_pct"]), "(Current - LY) / LY"),
    (f"{rt[:-1]} Share %", m.fmt_pct(c["share"]), "Peso face ao total Leads + Deals"),
])
st.write("")
ui.note(m.comparison_note(df_all, sel_q))
series = m.quarter_series(df, quarters, record_type, measure)
st.plotly_chart(charts.quarter_combo(series, sel_label, measure), width="stretch")

t1, t2 = st.columns(2)
for col, dim, title in ((t1, "originator", "Por Originator"), (t2, "platform", "Por Platform")):
    pv = m.quarter_pivot(df, sel_q, record_type, dim, measure)
    col.markdown(f"##### {title}")
    if measure == "amount":
        pv = pv.map(m.fmt_eur_short)
    else:
        pv = pv.astype(int)
    col.dataframe(pv, width="stretch", height=420)
