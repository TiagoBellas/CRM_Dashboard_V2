# 02 — Mapeamento Power BI → Databricks

Onde está implementada cada peça do modelo Power BI. Útil para manutenção e para
responder à pergunta "onde está a medida X?".

**Princípio de desenho:**
- Lógica **por linha** (Power Query e colunas calculadas DAX) → SQL, em `silver.pipeline`
  (determinística) ou `gold.vw_pipeline_all` (depende da data de hoje).
- Lógica **agregada** (medidas DAX) → funções Python em `app/crm_app/metrics.py`, aplicadas
  aos dados já filtrados (o equivalente ao contexto de filtro do DAX).
- Segurança (RLS) → views `gold` com `current_user()` + tabelas de pares utilizador/registo.

## 1. Power Query

| Passo PQ (tabela Pipeline) | Implementação (`sql/20_silver_pipeline.sql`, CTE `pq`/`pq2`) |
|---|---|
| `Sql.Database(... rpt.vw_CRMReportDealPipeline)` | `sql/10_bronze_ingest.sql` → `bronze.crm_deal_pipeline` |
| Replace `Closed`→`Won` em ActiveStage | `replace(ActiveStage,'Closed','Won')` |
| Rename Template→Vertical, CentralMD→Central MD, OriginatorName→Originator | colunas `vertical`, `central_md`, `originator` |
| Replace `NBO Stage`→`NBO / Preliminary Bids` | `replace(LastDealStatus, …)` |
| Remover `SpA`, `, SA`, `Ltd`, `BV`, `, Lda` de Platform | `trim(replace(…))` (o `trim` é um acréscimo; sem impacto nos dados atuais) |
| Segment: texto após o último `" - "` | `regexp_extract(Segment,'^.* - (.*)$',1)` |
| Segmentos fora da lista → `Other` | `LEFT JOIN ref.segment_mapping` + `coalesce(…,'Other')` (ver A4) |
| Platform `""`→`Other` | `CASE WHEN platform_cleaned = '' THEN 'Other'` |
| Leads: rename AmountInEuro→Amount (€) | `silver.leads.amount_eur` (+ coluna `source_env` DEV/PRD) |
| RLS_UserAccess_Raw: Excel, colunas, split Country por "/" | `src/crm_etl/rls.py` (notebook `nb_load_rls.py`) → `ref.rls_user_access_raw` |
| User_Access (dados colados) | `sql/11_bronze_all_users.sql` + `silver.crm_users` + `gold.vw_crm_users` |
| LastRefresh `DateTime.LocalNow()` | `gold.vw_last_refresh` (`max(_processed_at)`) |

## 2. Colunas calculadas DAX (todas validadas pelo teste de paridade)

| Coluna DAX | Coluna SQL | Onde |
|---|---|---|
| Stage Snapshot / Stage Snapshot Index | `stage_snapshot`, `stage_snapshot_index` | silver |
| Terminal Snapshot / v2 / 2 | `terminal_snapshot`, `terminal_snapshot_v2`, `terminal_snapshot_2` | silver |
| Decomp Closure Reason | `decomp_closure_reason` | silver |
| CRM Record URL (+ medida Base URL) | `crm_record_url` (URL base em `ref.app_config`) | silver |
| Month Start, Month Year, Pipeline Created Month Start | `month_start`, `month_year` | silver |
| Quarter Start/Number/Label/Sort/Year | `quarter_*` | silver |
| DQ Expected Terminal/Stage Name/Stage Snapshot | `dq_expected_*` | silver |
| DQ Lead Rejected / Deal Lost / Stage Classification / Source State Conflict / Has / Primary / Severity / Description / Amount | `dq_*` | silver |
| RLS Match Platform / Country / Scope | `rls_match_platform`, `rls_match_country` | silver |
| Stage Age Days (Snapshot) | `stage_age_days_snapshot` | gold (usa a data de hoje) |
| Time in Stage | `time_in_stage` | gold |
| Average Deal Age Column | `average_deal_age_days` | gold |
| Show Row - Closed This Year Or Blank (filtro de relatório) | `show_row_closed_this_year_or_blank` + `WHERE … = 1` em `gold.vw_pipeline` | gold |
| _DimStage[Stage (Display)], [Stage Group] | `ref.dim_stage` | ref |
| RLS Email / RLS Match Platform / RLS Country Token / RLS Access Type | `silver.rls_user_access` | silver |
| User Access Platform[Year/Month/MonthNumber] | `silver.crm_user_access_platform` | silver |

### Regras de tradução DAX → SQL usadas (importantes para manutenção)
1. DAX compara texto **sem** distinguir maiúsculas → SQL usa `upper(...)` dos dois lados.
2. Em DAX `BLANK <> "x"` é verdadeiro; em SQL `NULL <> 'x'` é desconhecido → usar `coalesce(col,'')`.
3. Em DAX `0 = BLANK()` é verdadeiro → `DQ Amount` marca também montantes 0.
4. `TRIM(SUBSTITUTE(x, UNICHAR(160), " "))` → `nullif(trim(replace(x, chr(160), ' ')), '')`.
5. `DATEDIFF(a, b, DAY)` conta mudanças de dia → `datediff(CAST(b AS DATE), CAST(a AS DATE))`.
6. `LOOKUPVALUE` → `LEFT JOIN ref.dim_stage ON upper(stage_name) = upper(...)`.

## 3. Tabelas calculadas

| Tabela DAX | Implementação |
|---|---|
| `_DimStage`, `_DimSegment` | `ref.dim_stage`, `ref.dim_segment` (`01_reference_data.sql`) |
| `_QuarterSelector` | `metrics.quarter_window()` (quarters dos últimos 24 meses) |
| `_QuarterComparison` | `metrics.quarter_comparison()` / `quarter_pivot()` |
| `SEC_AccessReconciliation` | `silver.sec_access_reconciliation` → `gold.vw_access_reconciliation` |
| `_CustomMeasures`, `DataQualityMeasures` | tabelas "contentor" de medidas → `metrics.py` |

## 4. Medidas DAX → `app/crm_app/metrics.py`

### Pipeline / KPIs (`kpis()`)
| Medida | Chave em `kpis()` |
|---|---|
| Total Pipeline Items | `total_items` |
| Win Count / Win Rate ("Conversion Rate %") | `win_count` / `win_rate` |
| Lost Deals / Lose Rate % / Drop-Off Rate | `lost_deals` / `lose_rate` |
| Open Deals / Non-Lost Pipeline | `open_deals` / `non_lost_pipeline` |
| Won Amount / Earned Pipeline Amount | `won_amount` |
| Average Deal Size | `avg_deal_size` |
| Average Deal Age, Average Deal Age (Won only) | `avg_deal_age()`, `avg_deal_age_won()` |
| PP 2026 Budget / PP Budget Target | `pp_budget` (ano corrente, países do pipeline filtrado) |
| % Achievement vs 2026 PP | `pp_achievement` |
| Pipeline Value Raw, 0. Pipeline Matrix Amount | `total_amount` |
| Deal Amount, Pipeline Count Label (formatação) | `fmt_eur_short()`, `fmt_int()` |

### Funil (`funnel()`, `avg_days_in_stage()`)
| Medida | Implementação |
|---|---|
| 1. Active / 1. Active (Per Platform) | `active_count` (usa `funnel_reached_stage_index` ≥ stage) |
| 1. Active Amount € / (Per Platform) | `active_amount` |
| 1. Funnel Total / 1. Funnel Total Amount € / Funnel Total Deals | `attrs["total_count"]`, `attrs["total_amount"]` |
| Percentage at Stage Count | `pct_count` |
| Lost Amount (At Stage) € | `lost_amount` (usa `funnel_lost_stage_index_amount`) |
| Lost Deals Count / Lost Deals (At Stage) | `lost_count` (usa `funnel_lost_stage_index_count`) |
| 1. Next Stage / 1. Next Stage € | `conversion_to_next` |
| Avg Days In Stage | `avg_days_in_stage()` (stage Lead usa a tabela Leads ativa — A1) |
| 2. Funnel Active HTML…, 2. Lost Bubble HTML…, Tooltip … HTML, Gap Mid-Aligned Count, Label Empty Space, Range Minimum | substituídas por `charts.funnel_chart()` / `lost_chart()` e pela tabela de detalhe |

> As medidas do funil iteravam a tabela inteira em DAX (`FILTER(ALLSELECTED(Pipeline), …)`).
> Na migração, o stage "alcançado"/"perdido" de cada registo é calculado **uma vez por linha**
> no SQL (`funnel_*` em `silver.pipeline`), e a medida passa a ser uma simples contagem/soma.

### Quarter (`quarter_*()`)
| Medidas | Implementação |
|---|---|
| Q. Selected/Previous/LY Quarter Start, Q. Selected Quarter End, Labels, Comparison Title, Matrix Comparison Subtitle | `quarter_comparison()` (`selected_label`, `previous_label`, `ly_label`) |
| Q. Leads/Deals Count, Current, Previous, LY (+ versões Amount) | `quarter_comparison()` (`current`, `previous`, `ly`; `measure="amount"`) |
| QoQ/YoY Change e % (Leads, Deals, Total Intake, Amount) | `qoq_change`, `qoq_pct`, `yoy_change`, `yoy_pct` |
| Q. Deal Share % / Lead Share % (+ Amount) | `share` |
| Q. Leads/Deals Comparison (+ Amount) | `quarter_pivot()` |
| Q. Data As Of, Q. Comparison Note | `comparison_note()` |
| Q. Deals Count Cumulative YTD (+Display), 0. Monthly Contribution %, 0. Deals Count, 0. Deals Added This Month | `monthly_by_segment()` |
| 0. Deals Trend + Cumulative … HTML (3 versões) | `charts.monthly_lines()` + tabela |

### Matrizes, ranking, DMS Usage, DQ
| Medidas | Implementação |
|---|---|
| 0. Pipeline Matrix Cell / Cell 2 / Cell 3, Pipeline Stage Matrix HTML (v3, v3 a, v4…) | `stage_matrix()` |
| Pipeline Count Label Platform / Country | percentagens em `by_dim_and_segment()` |
| Segment Rank …, Bump Chart Show, Visible CY Created Month | não usadas em nenhum visual → não migradas |
| Segment Legend HTML, 0. Country Header | substituídas pela legenda/título nativos |
| Latest Month, Total Licensed Users, Active Users, Non-Accessed Users, Login Rate % (+ Monthly) | `usage_latest()`, `usage_monthly()` |
| DQ Affected Items/Leads/Deals/Amount, DQ Critical Items, DQ Missing Amount, DQ Invalid Dates | `dq_summary()` |
| Average Lead Age, Average Lead Size, Average Lead/Approval Age (Label), Conversion Deal to Lead, Conversion Rate, Invested Amount Label, Won YTD (Actual), Won Year-End Projection | não usadas em visuais → não migradas (fáceis de acrescentar em `metrics.py` se necessário) |
| Last Refresh Label | cabeçalho de todas as páginas (`ui.header()`) |

## 5. RLS

| Power BI | Databricks |
|---|---|
| Role `RLS_Dynamic` na tabela Pipeline | `gold.vw_pipeline` / `vw_pipeline_dq`: `EXISTS` sobre `silver.rls_user_access` (GLOBAL) e `silver.pipeline_user_access` (pares e-mail/registo) com `lower(current_user())` |
| Filtro na tabela RLS_UserAccess_Raw | `gold.vw_my_access` |
| Membros do workspace vêem tudo | grupo `crm_report_admins` (`is_account_group_member`) |
| Leads (sem RLS explícita no PBI) | `gold.vw_leads`: mesma regra aplicada por plataforma/país do lead |

## 6. Se o volume crescer
Hoje cada utilizador carrega o seu subconjunto (~10 mil linhas) uma vez e os filtros são
aplicados em memória. Acima de ~500 mil linhas por utilizador, mova os filtros para o SQL:
em `app/crm_app/data.py` acrescente um `WHERE` com os valores de `FilterState` (parâmetros
nomeados `:platform0, :platform1…`) e mantenha `metrics.py` igual.
