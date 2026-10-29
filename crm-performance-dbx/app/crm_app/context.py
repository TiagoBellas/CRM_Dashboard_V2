"""Contexto partilhado entre páginas (utilizador + dados em cache)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from crm_app import data
from crm_app.db import UserContext
from crm_app.filters import apply_filters


def user() -> UserContext:
    return st.session_state["user"]


def today() -> date:
    return date.today()


def pipeline_all() -> pd.DataFrame:
    """Todos os registos que o utilizador pode ver (RLS aplicada), sem filtros."""
    u = user()
    return data.load_pipeline(u.email, u)


def pipeline(ignore: set[str] | None = None) -> pd.DataFrame:
    """Registos com os filtros globais aplicados."""
    return apply_filters(pipeline_all(), ignore=ignore)


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin"))
