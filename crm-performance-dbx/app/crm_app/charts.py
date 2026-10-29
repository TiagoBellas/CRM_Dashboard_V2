"""Gráficos Plotly (substituem os visuais nativos e os visuais HTML custom do PBI)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from crm_app import metrics as m

FONT = dict(family="Segoe UI, Arial, sans-serif", size=12)
SEG_COLOR_MAP = {s: c for (s, _, _), c in zip(m.SEGMENTS, m.SEGMENT_COLORS)}


def _layout(fig: go.Figure, height: int = 380, **kw) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), font=FONT,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1, xanchor="right"), **kw)
    return fig


def funnel_chart(f: pd.DataFrame, value: str = "amount") -> go.Figure:
    """'DEAL PIPELINE' (HTML 2. Funnel Active HTML (Amount €) 2)."""
    vals = f["active_amount"] if value == "amount" else f["active_count"]
    pct = f["pct_amount"] if value == "amount" else f["pct_count"]
    text = [(m.fmt_eur_short(v, space=False) if value == "amount" else m.fmt_int(v)) + f"  ({m.fmt_pct(p)})"
            for v, p in zip(vals, pct)]
    fig = go.Figure(go.Funnel(
        y=f["stage_name"], x=vals, text=text, textinfo="text", textposition="auto",
        marker=dict(color=[m.STAGE_COLORS[i] for i in f["stage_index"]]),
        connector=dict(line=dict(color="#d6dce2", width=1)),
        hovertemplate="%{y}<br>%{text}<extra></extra>"))
    return _layout(fig, 430, title="DEAL PIPELINE", showlegend=False)


def lost_chart(f: pd.DataFrame, value: str = "amount") -> go.Figure:
    """'DROP-OFF' (HTML 2. Lost Bubble HTML (Amount €) 2)."""
    d = f[f["stage_index"] <= 5].copy()
    vals = d["lost_amount"] if value == "amount" else d["lost_count"]
    text = [m.fmt_eur_short(v, space=False) if value == "amount" else m.fmt_int(v) for v in vals]
    fig = go.Figure(go.Bar(y=d["stage_name"], x=vals, orientation="h", text=text, textposition="outside",
                           marker_color="#DC5B57", hovertemplate="%{y}<br>%{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    top = float(vals.fillna(0).max() or 1)
    fig.update_xaxes(visible=False, range=[0, top * 1.35])
    fig.update_traces(cliponaxis=False)
    return _layout(fig, 430, title="DROP-OFF (perdidos no stage)", showlegend=False)


def quarter_combo(series: pd.DataFrame, selected_label: str, value: str = "count") -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ["#0f617d" if l == selected_label else "#76d5ff" for l in series["quarter_label"]]
    text = [m.fmt_eur_short(v, False) if value == "amount" else m.fmt_int(v) for v in series["value"]]
    fig.add_bar(x=series["quarter_label"], y=series["value"], name="Current", marker_color=colors,
                text=text, textposition="outside", secondary_y=False)
    fig.add_scatter(x=series["quarter_label"], y=series["qoq_pct"], name="QoQ %", mode="lines+markers",
                    line=dict(color="#DD915F"), secondary_y=True)
    fig.update_yaxes(tickformat=".0%", secondary_y=True, showgrid=False)
    return _layout(fig, 360, title="Evolução por quarter (data de criação)")


def stacked_100(d: pd.DataFrame, dim: str, value: str, horizontal: bool = False) -> go.Figure:
    text = [m.fmt_pct(p, 0) for p in d["pct"]]
    hover = [m.fmt_eur_short(v) if value == "amount" else m.fmt_int(v) for v in d["value"]]
    args = dict(color="segment", color_discrete_map=SEG_COLOR_MAP, text=text,
                custom_data=[hover], category_orders={"segment": [s for s, _, _ in m.SEGMENTS]})
    if horizontal:
        fig = px.bar(d, y=dim, x="pct", orientation="h", **args)
        fig.update_xaxes(tickformat=".0%", title=None)
        fig.update_yaxes(title=None, autorange="reversed")
    else:
        fig = px.bar(d, x=dim, y="pct", **args)
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_xaxes(title=None)
    fig.update_traces(hovertemplate="%{fullData.name}<br>%{customdata[0]} (%{text})<extra></extra>",
                      textposition="inside")
    return _layout(fig, 460, barmode="stack")


def donut_segments(df: pd.DataFrame) -> go.Figure:
    g = df.groupby("segment")["record_id"].nunique().reset_index()
    fig = px.pie(g, names="segment", values="record_id", hole=.55, color="segment",
                 color_discrete_map=SEG_COLOR_MAP)
    fig.update_traces(textinfo="percent", hovertemplate="%{label}: %{value}<extra></extra>")
    return _layout(fig, 380, title="Records by Segment")


def monthly_lines(pv: pd.DataFrame, monthly: pd.DataFrame, mode: str = "bars") -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    x = [f"{c:%b %Y}" for c in pv.columns]
    for seg in pv.index:
        y = pv.loc[seg].values
        if mode == "bars":
            fig.add_bar(x=x, y=y, name=seg, marker_color=SEG_COLOR_MAP.get(seg), secondary_y=False)
        else:
            fig.add_scatter(x=x, y=y, name=seg, mode="lines+markers",
                            line=dict(color=SEG_COLOR_MAP.get(seg)), secondary_y=False)
    mm = monthly.set_index("month_start").reindex(pv.columns)
    fig.add_scatter(x=x, y=mm["cumulative_ytd"].values, name="Cumulative YTD", mode="lines+markers+text",
                    text=mm["cumulative_ytd"].values, textposition="top center",
                    line=dict(color="#1f4964", dash="dot", width=3), secondary_y=True)
    fig.update_yaxes(title="Novos por mês", secondary_y=False)
    fig.update_yaxes(title="Acumulado no ano", secondary_y=True, showgrid=False)
    if mode == "lines":
        fig.update_yaxes(type="log", secondary_y=False)
    return _layout(fig, 460, barmode="stack")


def usage_by_platform(byp: pd.DataFrame) -> go.Figure:
    d = byp.reset_index()
    fig = go.Figure()
    fig.add_bar(x=d["platform"], y=d["active_users"], name="Active Users", marker_color="#0f617d")
    fig.add_bar(x=d["platform"], y=d["non_accessed_users"], name="Non-Accessed Users", marker_color="#d6dce2")
    fig.update_layout(barmode="stack", barnorm="percent")
    fig.update_yaxes(ticksuffix="%")
    return _layout(fig, 400, title="Utilizadores ativos vs. sem acesso (último mês)")


def bar_counts(s: pd.Series, title: str) -> go.Figure:
    fig = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h", marker_color="#0092d1",
                           text=s.values, textposition="outside"))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, 300, title=title, showlegend=False)
