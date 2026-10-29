"""DMS Usage (utilização do CRM por plataforma e último login dos utilizadores)."""
import streamlit as st

from crm_app import charts, context, data, metrics as m, ui

ui.header("DMS Usage", "Utilizadores licenciados vs. ativos no CRM")
u = context.user()
usage = data.load_usage(u.email, u)
if usage.empty:
    st.info("Sem dados de utilização.")
    st.stop()
lt = m.usage_latest(usage)
ui.kpi_row([
    ("Licensed Users", m.fmt_int(lt["licensed"]), f"Mês: {lt['month']:%b %Y}" if lt["month"] is not None else ""),
    ("Active Users", m.fmt_int(lt["active"]), "Último mês disponível"),
    ("Login Rate %", m.fmt_pct(lt["rate"]), "Active / Licensed"),
])
st.write("")
c1, c2 = st.columns([3, 2])
c1.plotly_chart(charts.usage_by_platform(lt["by_platform"]), width="stretch")
monthly = m.usage_monthly(usage)
years = sorted(monthly["year"].unique())
y = c2.selectbox("Ano", years, index=len(years) - 1, key="us_year")
mt = monthly[monthly["year"] == y][["month_name", "licensed_users", "active_users", "non_accessed_users", "login_rate"]]
mt = mt.rename(columns={"month_name": "Month", "licensed_users": "Licensed", "active_users": "Active",
                        "non_accessed_users": "Non-Accessed", "login_rate": "Login Rate %"})
c2.dataframe(mt, hide_index=True, width="stretch",
             column_config={"Login Rate %": st.column_config.NumberColumn(format="percent")})

users = data.load_crm_users(u.email, u)
if not users.empty:
    st.markdown("#### Último login registado")
    order = ["In the last 30 days", "In the last 60 days", "In the last 90 days", "More than 90 days",
             "No access recorded"]
    bu = st.multiselect("Business Unit", sorted(users["business_unit"].dropna().unique()), key="us_bu",
                        placeholder="Todas")
    uu = users[users["business_unit"].isin(bu)] if bu else users
    s = uu["last_login_range"].value_counts().reindex(order).fillna(0).astype(int)
    a, b = st.columns([1, 2])
    a.plotly_chart(charts.bar_counts(s, "Last Login Recorded"), width="stretch")
    b.dataframe(uu[["user_name", "title", "business_unit", "last_login", "logins_done", "last_login_range"]],
                hide_index=True, width="stretch", height=300)
