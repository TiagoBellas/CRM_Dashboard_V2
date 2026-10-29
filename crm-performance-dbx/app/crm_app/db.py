"""
Acesso a dados.

Três modos:
  * databricks + obo : a query corre COM A IDENTIDADE DO UTILIZADOR (token recebido no
                       cabeçalho x-forwarded-access-token). O Unity Catalog aplica a
                       RLS da view gold.vw_pipeline automaticamente. RECOMENDADO.
  * databricks + sp  : a query corre com o service principal da app; a app aplica a
                       regra RLS passando o e-mail do utilizador (x-forwarded-email).
  * duckdb           : demo local com dados sintéticos (sem Databricks).

Regras de segurança (boas práticas Databricks para OBO):
  - o token do utilizador é lido EM CADA pedido e nunca é guardado;
  - se o token faltar em modo OBO a app falha "fechada" (não troca para o SP).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from crm_app.config import Settings, get_settings


@dataclass(frozen=True)
class UserContext:
    email: str
    name: str
    access_token: str | None


class AuthError(RuntimeError):
    pass


def current_user() -> UserContext:
    settings = get_settings()
    headers = {}
    try:
        headers = {k.lower(): v for k, v in st.context.headers.items()}
    except Exception:  # fora de um pedido Streamlit (ex.: testes)
        headers = {}
    email = (headers.get("x-forwarded-email") or headers.get("x-forwarded-preferred-username") or "").lower()
    name = headers.get("x-forwarded-preferred-username") or email
    token = headers.get("x-forwarded-access-token")
    if settings.is_demo:
        return UserContext(email=email or "demo.user@example.com", name=name or "Demo User", access_token=None)
    if not email:
        raise AuthError("Não foi possível identificar o utilizador (cabeçalho x-forwarded-email em falta).")
    if settings.auth_mode == "obo" and not token:
        raise AuthError(
            "A app está em modo 'user authorization' mas não recebeu o token do utilizador. "
            "Confirme que o scope 'sql' foi adicionado à app e que o utilizador deu consentimento."
        )
    return UserContext(email=email, name=name, access_token=token)


def catalog() -> str:
    s = get_settings()
    return Path(s.demo_db_path).stem if s.is_demo else s.catalog


def run_query(sql: str, params: dict | None = None, user: UserContext | None = None,
              as_app: bool = False) -> pd.DataFrame:
    """Executa SQL (parâmetros nomeados :nome) e devolve um DataFrame."""
    settings = get_settings()
    sql = sql.replace("{catalog}", catalog())
    params = params or {}
    if settings.is_demo:
        return _run_duckdb(settings, sql, params)
    return _run_databricks(settings, sql, params, user, as_app)


# --------------------------------------------------------------------------- #
def _run_duckdb(settings: Settings, sql: str, params: dict) -> pd.DataFrame:
    import duckdb

    sql = re.sub(r"(?<![:\w]):([a-zA-Z_]\w*)", r"$\1", sql)
    sql = sql.replace("current_date()", "current_date")
    con = duckdb.connect(settings.demo_db_path, read_only=True)
    try:
        return con.execute(sql, params).df()
    finally:
        con.close()


def _run_databricks(settings: Settings, sql: str, params: dict, user: UserContext | None,
                    as_app: bool) -> pd.DataFrame:
    from databricks import sql as dbsql
    from databricks.sdk.core import Config

    if not settings.warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID não definido (recurso 'sql-warehouse' em falta na app).")
    cfg = Config()  # lê DATABRICKS_HOST / DATABRICKS_CLIENT_ID / SECRET injetados pela app
    http_path = f"/sql/1.0/warehouses/{settings.warehouse_id}"
    use_user_token = settings.auth_mode == "obo" and not as_app
    if use_user_token:
        if user is None or not user.access_token:
            raise AuthError("Token do utilizador em falta (modo OBO).")
        conn = dbsql.connect(server_hostname=cfg.host, http_path=http_path, access_token=user.access_token)
    else:
        conn = dbsql.connect(server_hostname=cfg.host, http_path=http_path,
                             credentials_provider=lambda: cfg.authenticate)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall_arrow().to_pandas()
    finally:
        conn.close()
