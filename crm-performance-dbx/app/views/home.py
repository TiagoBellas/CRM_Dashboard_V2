"""Home - visão geral (página 'Home' do PBI)."""
import plotly.express as px
import streamlit as st

from crm_app import context, metrics as m, ui

ui.header("Home", "Leads e Deals do CRM")
ui.note("Leads and closed deals from before the current year have been permanently removed from the "
        "dashboard (filtro de relatório 'Closed This Year Or Blank').")
df = context.pipeline()
if ui.empty_guard(df):
    st.stop()

k = m.kpis(df, today=context.today())
leads = int((df["record_type"].str.upper() == "LEAD").sum())
deals = int((df["record_type"].str.upper() == "DEAL").sum())
st.write("")
ui.kpi_row([
    ("Registos", m.fmt_int(k["total_items"]), f"{leads:,} leads · {deals:,} deals"),
    ("Valor total", m.fmt_eur_short(k["total_amount"]), "Soma de Amount (€)"),
    ("Pipeline não perdido", m.fmt_eur_short(k["non_lost_pipeline"]), f"{k['open_deals']:,} registos"),
    ("Won", m.fmt_eur_short(k["won_amount"]), f"{k['win_count']:,} registos"),
    ("Conversion Rate", m.fmt_pct(k["win_rate"]), "Win Count / Registos"),
])
st.write("")
c1, c2 = st.columns(2)
g = df.groupby("terminal_snapshot")["record_id"].nunique().reset_index()
fig = px.pie(g, names="terminal_snapshot", values="record_id", hole=.55, title="Registos por estado",
             color="terminal_snapshot",
             color_discrete_map={"Active": "#0092d1", "Won": "#33AE81", "Lost": "#DC5B57"})
c1.plotly_chart(fig, width="stretch")
s = df.groupby("stage_snapshot")["amount_eur"].sum().sort_index()
fig2 = px.bar(x=s.values, y=s.index, orientation="h", title="Valor por stage (€)",
              text=[m.fmt_eur_short(v) for v in s.values])
fig2.update_traces(marker_color="#0f617d")
fig2.update_layout(yaxis_title=None, xaxis_title=None, yaxis=dict(autorange="reversed"))
c2.plotly_chart(fig2, width="stretch")

st.markdown("#### Páginas")
st.page_link("views/funnel.py", label="Deal Funnel - funil por stage, perdas e KPIs de conversão", icon="🔻")
st.page_link("views/quarter.py", label="Quarter Performance - quarter selecionado vs anterior vs ano anterior", icon="📅")
st.page_link("views/matrix.py", label="Pipeline Matrix - Segmento/Plataforma x Stage", icon="🧮")
st.page_link("views/origination.py", label="Originação por Plataforma / País", icon="🌍")
st.page_link("views/records.py", label="Lista de registos com ligação ao CRM", icon="📋")
