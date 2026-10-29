"""Notes & Glossary (página oculta 'Notes & Glossary' do PBI, agora visível)."""
import streamlit as st

from crm_app import context, data, ui

ui.header("Notes & Glossary", "Definições usadas no relatório")
u = context.user()
leads = data.load_leads(u.email, u)
src = leads["source_env"].iloc[0] if not leads.empty and "source_env" in leads else "n/d"
st.markdown(f"""
**GENERAL INFORMATION**  
Each record is extracted from the database that stores the information entered in the CRM. It can be a
**Lead** or a **Deal** (RecordType) and comes from multiple source systems (SourceSystem: CRM, SLS or MCP).

- **Lead**: an opportunity at the screening stage, before it becomes a Deal.
- **Deal**: an opportunity under evaluation or negotiation.
- **Platform**: the group entity associated with the record.
- **Segment**: investment strategy (9 categories; unrecognised values are mapped to *Other*).
- **Amount (€)**: AmountInEuro, already converted to euros in the database.

**STAGES (funnel order)**  
1 Lead › 2 Early Prospect › 3 NBO / Preliminary Bids › 4 In Due Diligence › 5 IC Approved › 6 Won, Closing › 7 Won.
Index 0 is Lost. *Stage* = Stage Snapshot (stage atual; para perdidos, o stage onde foram perdidos).
*Status* = Active / Won / Lost (Terminal Snapshot).

**PERIODS (Quarter Performance)**  
Selected Quarter: the quarter chosen in the filter; if none, the most recent quarter in the data.
Previous: the immediately preceding quarter. LY: the same quarter in the previous year.
Quarters are measured by **creation date (CreatedOn)**, never by closing date.
QoQ % = (Current − Previous) / Previous · YoY % = (Current − LY) / LY.
Quarter in progress = partial; Previous and LY = complete. No adjustment is made for elapsed days.

**REPORT FILTER**  
Records closed before the current year are not shown (only open records or closed this year).

**CRM USAGE**  
Licensed / Active Users: latest month available. Login Rate % = Active / Licensed.

**SECURITY**  
Data is filtered by the e-mail of the signed-in user (Central/All = everything; All Portugal = Portugal;
otherwise Platform + Country). A user with no row in the access list sees no data.

**DATA SOURCES**  
Pipeline, Investment Allocation, CRM usage: Synapse PRD. Leads table (only used for the average time in
the *Lead* stage): **{src}** — pending business decision (DEV vs PRD).
""")
