"""Administração: Data Quality (páginas ocultas DQ / DQ Notes), reconciliação de acessos e Leads DEV x PRD."""
import streamlit as st

from crm_app import context, data, metrics as m, ui

ui.header("Data Quality & Acessos", "Página de administração (visível apenas para admins)")
u = context.user()
t1, t2, t3, t4 = st.tabs(["Qualidade de dados", "Reconciliação de acessos", "Leads DEV vs PRD", "Os meus acessos"])

with t1:
    dq = data.load_pipeline_dq(u.email, u)
    s = m.dq_summary(dq)
    ui.kpi_row([
        ("Itens afetados", m.fmt_int(s["affected_items"]), f"{s['affected_leads']} leads · {s['affected_deals']} deals"),
        ("Críticos", m.fmt_int(s["critical_items"]), "Severity = Critical"),
        ("Valor afetado", m.fmt_eur_short(s["affected_amount"]), ""),
        ("Sem montante", m.fmt_int(s["missing_amount"]), "AmountInEuro vazio"),
        ("Datas inválidas", m.fmt_int(s["invalid_dates"]), "ClosedOn < CreatedOn"),
    ])
    st.write("")
    issues = dq[dq["dq_has_classification_issue"] == 1]
    st.dataframe(issues.groupby(["dq_severity", "dq_primary_issue"]).agg(
        registos=("record_id", "nunique"), valor=("amount_eur", "sum")).reset_index(),
        hide_index=True, width="stretch")
    st.dataframe(issues[["record_name", "record_type", "source_system", "active_stage", "state_name",
                         "lead_status", "last_deal_status", "stage_snapshot", "terminal_snapshot",
                         "dq_expected_stage_snapshot", "dq_issue_description", "crm_record_url"]],
                 hide_index=True, width="stretch", height=380,
                 column_config={"crm_record_url": st.column_config.LinkColumn("CRM", display_text="abrir")})

with t2:
    rec = data.load_admin_table("vw_access_reconciliation", u.email, u)
    if rec is None:
        st.warning("Sem permissão para gold.vw_access_reconciliation.")
    else:
        st.caption("Equivalente à tabela SEC_AccessReconciliation. 'CHECK' = perfil sem correspondência no pipeline.")
        st.dataframe(rec, hide_index=True, width="stretch")

with t3:
    cmp_ = data.load_admin_table("vw_leads_source_comparison", u.email, u)
    if cmp_ is None:
        st.warning("Sem permissão para gold.vw_leads_source_comparison.")
    else:
        st.markdown("Comparação das duas origens da tabela **Leads** (achado A1). A origem ativa é definida "
                    "pelo parâmetro `leads_source_active` do job.")
        st.dataframe(cmp_, hide_index=True, width="stretch",
                     column_config={"pct_matching_pipeline": st.column_config.NumberColumn(format="percent")})

with t4:
    mine = data.load_admin_table("vw_my_access", u.email, u)
    st.dataframe(mine if mine is not None else [], hide_index=True, width="stretch")
