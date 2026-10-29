"""Leads & Deals Table + Top Platform Leads."""
import streamlit as st

from crm_app import context, ui

ui.header("Leads & Deals Table", "Lista de registos com ligação direta ao CRM")
df = context.pipeline()
preset = st.segmented_control(
    "Vista", ["Todos os registos", "Top Platform Leads"], default="Todos os registos", key="rc_preset",
    help="Top Platform Leads = Leads ativos no stage '1. Lead' (página 'Top Platform Leads' do PBI).")
if preset == "Top Platform Leads":
    df = df[(df["stage_snapshot"] == "1. Lead") & (~df["terminal_snapshot"].isin(["Lost", "Won"]))]
q = st.text_input("Pesquisar por nome", key="rc_q", placeholder="parte do nome do registo...")
if q:
    df = df[df["record_name"].fillna("").str.contains(q, case=False, regex=False)]
if ui.empty_guard(df):
    st.stop()
ui.records_table(df, key="records", height=620, extra_cols=["central_md", "fund_name", "source_system"])
