"""
Carregamento de dados (com cache por utilizador).

Estratégia: o volume de dados é pequeno (~10 mil registos), por isso cada
utilizador carrega UMA VEZ o seu subconjunto já filtrado pela RLS (cache de
10 min) e todos os filtros/medidas são calculados em memória (pandas) - tal como
o motor VertiPaq do Power BI. Se o volume crescer muito (> ~500 mil linhas),
mova os filtros para o WHERE das queries (ver docs/02_Mapeamento_DAX_SQL.md).

IMPORTANTE: a chave de cache inclui SEMPRE o e-mail do utilizador, para que
os dados de um utilizador nunca sejam servidos a outro.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from crm_app.config import get_settings
from crm_app.db import UserContext, run_query

TTL = get_settings().cache_ttl_seconds

DATE_COLS = ["created_on", "modified_on", "closed_on", "passed_to_nbo", "passed_to_dd",
             "passed_to_ic", "passed_to_won", "month_start", "quarter_start"]

PIPELINE_SQL_OBO = "SELECT * FROM {catalog}.gold.vw_pipeline"
PIPELINE_SQL_SP = """
SELECT p.*
FROM {catalog}.gold.vw_pipeline_all p
WHERE p.show_row_closed_this_year_or_blank = 1
  AND (   EXISTS (SELECT 1 FROM {catalog}.gold.vw_rls_user_access_all a
                  WHERE a.rls_email = :email AND a.rls_access_type = 'GLOBAL')
       OR p.record_id IN (SELECT record_id FROM {catalog}.gold.vw_pipeline_user_access_all
                          WHERE rls_email = :email))
"""
DQ_SQL_OBO = "SELECT * FROM {catalog}.gold.vw_pipeline_dq"
DQ_SQL_SP = PIPELINE_SQL_SP.replace("WHERE p.show_row_closed_this_year_or_blank = 1\n  AND", "WHERE")
LEADS_SQL_OBO = "SELECT * FROM {catalog}.gold.vw_leads"
LEADS_SQL_SP = """
SELECT l.* FROM {catalog}.gold.vw_leads_all l
WHERE l.is_active_source = 1
  AND (   EXISTS (SELECT 1 FROM {catalog}.gold.vw_rls_user_access_all a
                  WHERE a.rls_email = :email AND a.rls_access_type = 'GLOBAL')
       OR EXISTS (SELECT 1 FROM {catalog}.gold.vw_leads_user_access_all x
                  WHERE x.rls_email = :email AND x.source_env = l.source_env AND x.record_id = l.record_id))
"""


def _sp() -> bool:
    s = get_settings()
    return (not s.is_demo) and s.auth_mode == "sp"


def _fix_types(df: pd.DataFrame) -> pd.DataFrame:
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("amount_eur", "amount_base", "exchange_rate"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=TTL, show_spinner="A carregar o pipeline...")
def load_pipeline(user_email: str, _user: UserContext) -> pd.DataFrame:
    sql = PIPELINE_SQL_SP if _sp() else PIPELINE_SQL_OBO
    return _fix_types(run_query(sql, {"email": user_email} if _sp() else {}, _user))


@st.cache_data(ttl=TTL, show_spinner="A carregar dados de qualidade...")
def load_pipeline_dq(user_email: str, _user: UserContext) -> pd.DataFrame:
    sql = DQ_SQL_SP if _sp() else DQ_SQL_OBO
    return _fix_types(run_query(sql, {"email": user_email} if _sp() else {}, _user))


@st.cache_data(ttl=TTL, show_spinner=False)
def load_leads(user_email: str, _user: UserContext) -> pd.DataFrame:
    sql = LEADS_SQL_SP if _sp() else LEADS_SQL_OBO
    return _fix_types(run_query(sql, {"email": user_email} if _sp() else {}, _user))


@st.cache_data(ttl=TTL, show_spinner=False)
def load_investment_allocation(user_email: str, _user: UserContext) -> pd.DataFrame:
    return run_query("SELECT * FROM {catalog}.gold.vw_investment_allocation", {}, _user)


@st.cache_data(ttl=TTL, show_spinner=False)
def load_usage(user_email: str, _user: UserContext) -> pd.DataFrame:
    df = run_query("SELECT * FROM {catalog}.gold.vw_crm_user_access_platform", {}, _user)
    df["month_start"] = pd.to_datetime(df["month_start"], errors="coerce")
    return df


@st.cache_data(ttl=TTL, show_spinner=False)
def load_crm_users(user_email: str, _user: UserContext) -> pd.DataFrame:
    return run_query("SELECT * FROM {catalog}.gold.vw_crm_users", {}, _user)


@st.cache_data(ttl=300, show_spinner=False)
def load_last_refresh(user_email: str, _user: UserContext):
    df = run_query("SELECT last_refresh_ts FROM {catalog}.gold.vw_last_refresh", {}, _user)
    return None if df.empty else pd.to_datetime(df.iloc[0, 0])


# ---- páginas de administração (só funcionam para quem tem permissão) -------
@st.cache_data(ttl=TTL, show_spinner=False)
def load_admin_table(view: str, user_email: str, _user: UserContext) -> pd.DataFrame | None:
    try:
        return run_query(f"SELECT * FROM {{catalog}}.gold.{view}", {}, _user)
    except Exception:
        return None
