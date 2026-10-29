"""
Filtros globais (equivalentes aos slicers sincronizados entre páginas no PBI).

Os filtros são desenhados na barra lateral pelo app.py (que corre em todas as
páginas) e guardados em st.session_state, por isso mantêm-se ao mudar de página.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import streamlit as st

BLANK = "(Blank)"

# (chave, etiqueta, coluna)
CATEGORICAL = [
    ("platform", "Platform", "platform"),
    ("country", "Country", "country_name"),
    ("segment", "Segment", "segment"),
    ("record_type", "Record Type", "record_type"),
    ("stage", "Stage", "stage_snapshot"),
    ("terminal", "Status (Active / Won / Lost)", "terminal_snapshot"),
    ("originator", "Originator", "originator"),
    ("central_md", "Central MD", "central_md"),
    ("fund", "Fund Name", "fund_name"),
    ("lead_status", "Lead Status", "lead_status"),
    ("vertical", "Vertical", "vertical"),
]


@dataclass
class FilterState:
    categorical: dict[str, list[str]] = field(default_factory=dict)
    created: tuple[date, date] | None = None
    closed: tuple[date, date] | None = None
    amount_min_m: float | None = None
    amount_max_m: float | None = None

    def active_count(self) -> int:
        n = sum(1 for v in self.categorical.values() if v)
        return n + sum(x is not None for x in (self.created, self.closed, self.amount_min_m, self.amount_max_m))


def _options(df: pd.DataFrame, col: str) -> list[str]:
    vals = df[col].dropna().astype(str).unique().tolist()
    vals = sorted(vals, key=lambda s: (s[:1].isdigit() is False, s))
    if df[col].isna().any():
        vals.append(BLANK)
    return vals


def render_sidebar(df: pd.DataFrame) -> FilterState:
    st.sidebar.markdown("### Filtros")
    if st.sidebar.button("Limpar todos os filtros", width="stretch"):
        for k in list(st.session_state.keys()):
            if k.startswith("flt_"):
                del st.session_state[k]
        st.rerun()

    state = FilterState()
    main = CATEGORICAL[:5]
    more = CATEGORICAL[5:]
    for key, label, col in main:
        state.categorical[key] = st.sidebar.multiselect(label, _options(df, col), key=f"flt_{key}",
                                                        placeholder="Todos")
    with st.sidebar.expander("Mais filtros"):
        for key, label, col in more:
            state.categorical[key] = st.multiselect(label, _options(df, col), key=f"flt_{key}",
                                                    placeholder="Todos")
        if st.checkbox("Filtrar por data de criação", key="flt_use_created"):
            lo, hi = df["created_on"].min(), df["created_on"].max()
            rng = st.date_input("Created On", value=(lo.date(), hi.date()), key="flt_created")
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                state.created = (rng[0], rng[1])
        if st.checkbox("Filtrar por data de fecho", key="flt_use_closed"):
            c = df["closed_on"].dropna()
            lo, hi = (c.min(), c.max()) if not c.empty else (pd.Timestamp.today(), pd.Timestamp.today())
            rng = st.date_input("Closed On", value=(lo.date(), hi.date()), key="flt_closed")
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                state.closed = (rng[0], rng[1])
        if st.checkbox("Filtrar por montante (M€)", key="flt_use_amount"):
            c1, c2 = st.columns(2)
            state.amount_min_m = c1.number_input("Mín.", min_value=0.0, value=0.0, step=1.0, key="flt_amin")
            state.amount_max_m = c2.number_input("Máx.", min_value=0.0, value=10000.0, step=10.0, key="flt_amax")
    n = state.active_count()
    if n:
        st.sidebar.caption(f"{n} filtro(s) ativo(s)")
    st.session_state["filter_state"] = state
    return state


def get_state() -> FilterState:
    return st.session_state.get("filter_state", FilterState())


def apply_filters(df: pd.DataFrame, state: FilterState | None = None, ignore: set[str] | None = None) -> pd.DataFrame:
    """Aplica os filtros. `ignore` permite ignorar filtros, como fazem algumas medidas
    DAX com REMOVEFILTERS (ex.: as páginas de Quarter ignoram as datas de criação)."""
    state = state or get_state()
    ignore = ignore or set()
    mask = pd.Series(True, index=df.index)
    colmap = {k: c for k, _, c in CATEGORICAL}
    for key, values in state.categorical.items():
        if not values or key in ignore:
            continue
        col = df[colmap[key]]
        m = col.astype(str).isin([v for v in values if v != BLANK])
        if BLANK in values:
            m |= col.isna()
        mask &= m
    if state.created and "created" not in ignore:
        lo, hi = pd.Timestamp(state.created[0]), pd.Timestamp(state.created[1]) + pd.Timedelta(days=1)
        mask &= (df["created_on"] >= lo) & (df["created_on"] < hi)
    if state.closed and "closed" not in ignore:
        lo, hi = pd.Timestamp(state.closed[0]), pd.Timestamp(state.closed[1]) + pd.Timedelta(days=1)
        mask &= (df["closed_on"] >= lo) & (df["closed_on"] < hi)
    if state.amount_min_m is not None and "amount" not in ignore:
        mask &= df["amount_eur"] >= state.amount_min_m * 1e6
    if state.amount_max_m is not None and "amount" not in ignore:
        mask &= df["amount_eur"] <= state.amount_max_m * 1e6
    return df[mask]
