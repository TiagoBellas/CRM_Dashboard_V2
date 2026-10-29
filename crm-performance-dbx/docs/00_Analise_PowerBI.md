# 00 — Análise do Power BI `CRM_Performance_Reporting_MVP_v1.pbix`

Este documento descreve o que existe no relatório original, como foi analisado e os
problemas encontrados que a migração corrige (ou que precisam de decisão de negócio).

## 1. Como foi feita a análise

O `.pbix` está no formato **PBIR** (definição do relatório em JSON). O modelo de dados
(`DataModel`) foi descodificado com a biblioteca `pbixray`, o que permitiu extrair:
o Power Query (M), as 158 medidas DAX, as colunas e tabelas calculadas, as relações,
a role RLS e **os próprios dados importados, incluindo as colunas calculadas já
materializadas**. Estes dados serviram de "verdade" para o teste de paridade
(`tests/test_parity.py`): o SQL do projeto reproduz **44 de 44 colunas calculadas DAX
sem nenhuma diferença** nos 10.172 registos, e a RLS dá exatamente o mesmo resultado
para os 241 utilizadores da lista de acessos.

Para repetir a extração: `python tools/extract_pbix_reference.py <ficheiro.pbix>`.

## 2. Inventário

| Item | Quantidade | Notas |
|---|---|---|
| Páginas | 23 | 15 visíveis, 8 ocultas (tooltips, DQ, notas, uma "to_be_Deleted") |
| Medidas DAX | 158 | ~25 geram HTML (até 46.816 caracteres cada) para visuais custom |
| Colunas calculadas | 40 | 37 na tabela `Pipeline` |
| Tabelas calculadas | 6 | `_DimStage`, `_DimSegment`, `_QuarterSelector`, `_QuarterComparison`, `SEC_AccessReconciliation`, `_CustomMeasures` |
| Relações | 7 | 3 muitos-para-muitos bidirecionais |
| Roles RLS | 1 | `RLS_Dynamic` (por e-mail) |
| Visuais custom | 2 | "HTML Content" (renderizam o HTML das medidas) |
| Bookmarks | 15 | alternância contagem/montante |

### 2.1 Fontes de dados

| Tabela PBI | Origem | Servidor / base |
|---|---|---|
| Pipeline | `rpt.vw_CRMReportDealPipeline` | `dynamicsynapseprod-ondemand…` / `dataverse_arrowcrm_org375adb08` (PRD) |
| Investment Allocation | `rpt.vw_InvestmentAllocation` | PRD |
| User Access Platform | `rpt.vw_CRMUserAccess` | PRD |
| **Leads** | `rpt.vw_CRMLeads` | **`dynamicsynapse-ondemand…` / `dataverse_arrowcrmdev_…` (DEV!)** |
| RLS_UserAccess_Raw | Excel `C:\Users\tbellas\OneDrive…\UserPlatformCountry 1.xlsx` | ficheiro local |
| User_Access | dados **colados** no modelo (Json comprimido) | estático |
| LastRefresh | `DateTime.LocalNow()` | calculado no refresh |

Todas as fontes SQL são views do **Azure Synapse Serverless** sobre o Dataverse
(Synapse Link). Volume: ~10 mil registos de pipeline — pequeno.

### 2.2 Modelo e relações relevantes

- `Pipeline[ActiveStage]` → `_DimStage[Stage Name]` (N:1). **Atenção:** as matrizes por
  stage usam esta relação, ou seja o stage **atual** (`ActiveStage`), e não o
  `Stage Snapshot`.
- `Pipeline[Segment]` → `_DimSegment[Segment Name]` (N:1).
- `Pipeline[LeadId]` ↔ `Leads[LeadId]` (M:M, bidirecional).
- `Pipeline[CountryName]` ↔ `Investment Allocation[CountryName]` (M:M, bidirecional):
  o orçamento é filtrado pelos países presentes no pipeline filtrado.
- `_QuarterSelector` é **desligada** de propósito (permite comparar quarters).

### 2.3 Páginas → nova app

| Página(s) Power BI | Página na Databricks App |
|---|---|
| Home | Home |
| Deal Funnel (+ tooltips Funnel Tooltip / €) | Deal Funnel |
| Lead & Deal Overview, Platform Deals Summary Table | Pipeline Matrix (alternância de linhas) |
| Quarter Performance, Leads Quarter Performance €, Deals Quarter Performance Qty, Deals Quarter Performance € | Quarter Performance (alternâncias Leads/Deals e Qtd/€) |
| New Leads by Segment, New Leads by Segment 2 | New Leads by Segment (barras / linhas) |
| Lead Origination by Platform & Country, Leads Segment by Country | Origination by Platform / Country |
| Leads by Originator | Leads by Originator |
| Leads & Deals Table, Top Platform Leads | Leads & Deals Table (vista "Top Platform Leads") |
| DMS Usage | DMS Usage |
| Notes & Glossary (oculta) | Notes & Glossary (visível) |
| DQ, DQ Notes (ocultas) + SEC_AccessReconciliation | Data Quality & Acessos (só admins) |
| Cumulative Deals_to_be_Deleted, Notes | não migradas (marcadas para apagar / notas técnicas) |

Os ~200 slicers repetidos/sincronizados em todas as páginas passam a **um único painel
de filtros global** na barra lateral, que se mantém ao mudar de página.

## 3. Achados (problemas e riscos)

| # | Gravidade | Achado | Tratamento na migração |
|---|---|---|---|
| **A1** | Alta | A tabela **Leads vem da base DEV**, as restantes de PRD. Nenhum LeadId de DEV existe no Pipeline (0%). Na base DEV não existe nenhum lead "Approved" com data de fecho, por isso o **tempo médio no stage Lead está sempre em branco** no PBI. | As **duas versões** são ingeridas; o parâmetro `leads_source_active` (por omissão `DEV`, igual ao PBI) escolhe a ativa. Página de Administração compara DEV vs PRD. **Decisão de negócio pendente.** |
| **A2** | Alta | A lista de acessos RLS lê um **Excel no OneDrive pessoal** de um colaborador. Se o ficheiro mudar de sítio, o refresh falha ou os acessos ficam desatualizados. | O ficheiro passa para um **Volume do Unity Catalog** (`ref.landing/rls/`), com permissões controladas e histórico. |
| **A3** | Média | `User_Access` (página DMS Usage) está **colada no modelo** — nunca é atualizada. | Lida diretamente de `crm.vAllUsers` (tarefa opcional). |
| **A4** | Média | A lista de segmentos válidos no Power Query tem **erros ortográficos** (`Oportunistic Credit`, `Investment Grande Asset-Backed`, `Real State Lending`). Valores escritos corretamente caem em "Other". Hoje 7.020 de 10.172 registos (69%) são "Other". | Tabela `ref.segment_mapping` aceita ambas as grafias e mapeia para o nome correto. Validar com o negócio porque pode alterar a distribuição por segmento. |
| A5 | Média | Filtro **oculto** ao nível do relatório: só aparecem registos abertos ou fechados no ano corrente (8.451 de 10.172). | Mantido (view `gold.vw_pipeline`) e explicado em todas as páginas. |
| A6 | Média | Inconsistências de dados na fonte (já identificadas na página DQ Notes): `StateName` não é harmonizado entre CRM/SLS/MCP; deals "Lost" no CRM com `ActiveStage` ativo. | Colunas DQ migradas; página de Administração mostra os casos com link para o CRM. |
| A7 | Baixa | Medidas DAX muito complexas que geram HTML (difíceis de manter) e várias versões duplicadas (`v3`, `v3 a`, `v4`, `2`…). | Substituídas por gráficos nativos; as regras de negócio foram isoladas em `metrics.py` com testes. |
| A8 | Baixa | `DQ Amount` marca também montantes **0** (em DAX `0 = BLANK()` é verdadeiro). | Comportamento replicado e documentado. |
| A9 | Baixa | A coluna URL do CRM compara `EntityName = "Deal"`, mas os valores reais são `arrow_loandeal`, `opportunity`… — funciona apenas pelo caminho alternativo. | Replicado tal como está (resultado idêntico). |
| A10 | Info | O `Investment Allocation` não tem a limpeza de sufixos de plataforma (ex.: "Eagle Street Partners Ltd"). Só é ligado por país, por isso não afeta os números. | Sem alteração. |

## 4. Regras de negócio essenciais (resumo)

- **Stage Snapshot**: stage atual; para deals perdidos usa `LastDealStatus` (o stage
  onde foi perdido), com "Early Prospect" por omissão; leads rejeitados ficam em "Lead".
- **Terminal Snapshot**: `Lost` (lead rejeitado, ou ActiveStage/StateName = Lost),
  `Won` (ActiveStage/StateName = Won), senão `Active`.
- **Funil**: um registo conta em todos os stages até ao que alcançou (cumulativo).
- **Quarter Performance**: quarters pela data de criação; Previous = quarter anterior;
  LY = mesmo quarter do ano anterior; quarter em curso é parcial (sem ajuste).
- **RLS**: `Central | All` vê tudo; `All Portugal | Portugal` vê Portugal;
  restantes vêem a combinação Plataforma + País(es) da lista. Sem linha = sem dados.

O detalhe completo de cada medida está em `02_Mapeamento_DAX_SQL.md`.
