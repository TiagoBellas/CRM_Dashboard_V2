"""Deal Funnel (página 'Deal Funnel' do PBI + tooltips Funnel Tooltip / Funnel Tooltip €)."""
import pandas as pd
import streamlit as st

from crm_app import charts, context, data, metrics as m, ui

ui.header("Deal Funnel", "Registos que alcançaram cada stage e perdas por stage")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()
u = context.user()
value = st.segmented_control("Medida", ["Montante (€)", "Quantidade"], default="Montante (€)", key="fn_val")
value = "count" if value == "Quantidade" else "amount"

ia = data.load_investment_allocation(u.email, u)
k = m.kpis(df, ia, context.today())
ui.kpi_row([
    ("Deals", m.fmt_int(k["total_items"]), "Registos no contexto"),
    ("Conversion Rate %", m.fmt_pct(k["win_rate"]), "Win Count / Registos"),
    ("Lose Rate %", m.fmt_pct(k["lose_rate"]), "(Lost + Rejected) / Registos"),
    (f"PP {context.today().year} Budget", m.fmt_eur_short(k["pp_budget"]), "Investment Allocation"),
    (f"% PP {str(context.today().year)[2:]} Achieved", m.fmt_pct(k["pp_achievement"]), "Won no ano / Budget"),
    ("Avg Deal Size", m.fmt_eur_short(k["avg_deal_size"]), "Valor / Registos"),
    ("Avg Deal Age (Won)", m.fmt_days(k["avg_deal_age_won"]), "Criação → Fecho"),
])
st.write("")
f = m.funnel(df)
c1, c2 = st.columns([3, 2])
c1.plotly_chart(charts.funnel_chart(f, value), width="stretch")
c2.plotly_chart(charts.lost_chart(f, value), width="stretch")

leads = data.load_leads(u.email, u)
days = m.avg_days_in_stage(df, leads, context.today())
detail = pd.DataFrame({
    "Stage": f["stage_name"],
    "Alcançaram (nº)": f["active_count"],
    "Alcançaram (€)": [m.fmt_eur_short(v) for v in f["active_amount"]],
    "% do total (€)": [m.fmt_pct(v) for v in f["pct_amount"]],
    "Conversão p/ stage seguinte": [m.fmt_pct(v) for v in f["conversion_to_next"]],
    "Perdidos no stage (nº)": f["lost_count"],
    "Perdidos no stage (€)": [m.fmt_eur_short(v) if v is not None else "" for v in f["lost_amount"]],
    "Tempo médio no stage": [m.fmt_days(days.get(s)) for s in f["stage_name"]],
})
with st.expander("Detalhe por stage (tooltip do funil)", expanded=True):
    st.dataframe(detail, hide_index=True, width="stretch")
    src = leads["source_env"].iloc[0] if not leads.empty and "source_env" in leads else "n/d"
    st.caption(f"Tempo no stage 'Lead' calculado sobre a tabela Leads (origem ativa: {src}). "
               "Ver Notes & Glossary.")

st.markdown("#### CRM Record list")
ui.records_table(df[df["active_stage"].str.upper() != "LOST"], key="funnel_records")
