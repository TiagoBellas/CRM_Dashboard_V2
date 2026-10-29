"""
CRM Performance Reporting - Databricks App
Ponto de entrada: autenticação, carregamento de dados, filtros globais e navegação.
Executar localmente em modo demo:  APP_BACKEND=duckdb streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from crm_app.config import get_settings

settings = get_settings()
st.set_page_config(page_title=settings.app_title, page_icon="📊", layout="wide")

from crm_app import data  # noqa: E402
from crm_app.db import AuthError, current_user  # noqa: E402
from crm_app.filters import render_sidebar  # noqa: E402
from crm_app.ui import inject_css  # noqa: E402

inject_css()

# 1) Utilizador ---------------------------------------------------------------
try:
    user = current_user()
except AuthError as exc:
    st.error(f"Erro de autenticação: {exc}")
    st.stop()
st.session_state["user"] = user

# 2) Dados (cache por utilizador) ---------------------------------------------
try:
    df_all = data.load_pipeline(user.email, user)
except Exception as exc:  # noqa: BLE001
    st.error("Não foi possível ler os dados do pipeline. Verifique as permissões no Unity Catalog "
             "(GRANT SELECT em gold.vw_pipeline) e o acesso ao SQL Warehouse.")
    with st.expander("Detalhe técnico"):
        st.exception(exc)
    st.stop()

try:
    st.session_state["last_refresh"] = data.load_last_refresh(user.email, user)
except Exception:  # noqa: BLE001
    st.session_state["last_refresh"] = None
st.session_state["is_admin"] = settings.is_demo or (
    data.load_admin_table("vw_access_reconciliation", user.email, user) is not None)

# 3) Barra lateral: utilizador + filtros globais ---------------------------------
st.sidebar.markdown(f"**{settings.app_title}**")
st.sidebar.caption(f"👤 {user.email}" + ("  ·  modo DEMO" if settings.is_demo else ""))
if df_all.empty:
    st.sidebar.warning("Sem dados visíveis para o seu utilizador. Se deveria ter acesso, peça a "
                       "inclusão na lista de acessos (RLS).")
render_sidebar(df_all)
if st.sidebar.button("Atualizar dados", help="Limpa a cache e volta a ler do Databricks"):
    st.cache_data.clear()
    st.rerun()

# 4) Navegação -------------------------------------------------------------------
V = Path(__file__).resolve().parent / "views"
pages = {
    "Visão geral": [
        st.Page(V / "home.py", title="Home", icon="🏠", default=True),
        st.Page(V / "funnel.py", title="Deal Funnel", icon="🔻"),
        st.Page(V / "matrix.py", title="Pipeline Matrix", icon="🧮"),
    ],
    "Performance": [
        st.Page(V / "quarter.py", title="Quarter Performance", icon="📅"),
        st.Page(V / "new_leads.py", title="New Leads by Segment", icon="📈"),
    ],
    "Originação": [
        st.Page(V / "origination.py", title="Origination by Platform / Country", icon="🌍"),
        st.Page(V / "originator.py", title="Leads by Originator", icon="🧑‍💼"),
    ],
    "Registos & utilização": [
        st.Page(V / "records.py", title="Leads & Deals Table", icon="📋"),
        st.Page(V / "usage.py", title="DMS Usage", icon="👥"),
        st.Page(V / "glossary.py", title="Notes & Glossary", icon="📖"),
    ],
}
if st.session_state["is_admin"]:
    pages["Administração"] = [st.Page(V / "admin.py", title="Data Quality & Acessos", icon="🛠️")]

st.navigation(pages).run()
