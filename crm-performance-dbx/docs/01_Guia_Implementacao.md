# 01 — Guia de Implementação passo a passo

Guia escrito para quem implementa **pela primeira vez** um projeto no Databricks.
Siga as fases pela ordem. Cada passo tem o **resultado esperado** para confirmar que
correu bem antes de avançar. Tempo estimado: 2–3 dias úteis (a maior parte é esperar por
acessos de outras equipas — peça-os logo no início, Fase 0).

> **Estratégia:** primeiro põe-se tudo a funcionar em **DEV com dados fictícios**
> (Fases 1–6, não depende de ninguém). Só depois se liga ao Synapse real (Fase 7) e se
> passa a produção (Fase 9). Assim os problemas de infraestrutura e de dados ficam separados.

---

## Índice

- [Fase 0 — Preparação e pedidos de acesso](#fase-0)
- [Fase 1 — Verificar o workspace Databricks](#fase-1)
- [Fase 2 — Grupos e identidades](#fase-2)
- [Fase 3 — Catálogo, schemas e volume](#fase-3)
- [Fase 4 — SQL Warehouse](#fase-4)
- [Fase 5 — Preparar o seu computador](#fase-5)
- [Fase 6 — Primeiro deploy em DEV com dados de exemplo](#fase-6)
- [Fase 7 — Ligar ao Synapse (dados reais) — DEV e PRD](#fase-7)
- [Fase 8 — Validação contra o Power BI (UAT)](#fase-8)
- [Fase 9 — Produção](#fase-9)
- [Fase 10 — Operação diária](#fase-10)
- [Anexo A — Resolução de problemas](#anexo-a)
- [Anexo B — Glossário Databricks](#anexo-b)

---

<a id="fase-0"></a>
## Fase 0 — Preparação e pedidos de acesso

### 0.1 Arquitetura (o que vai ser construído)

```
 Dataverse (CRM)                                    Unity Catalog: crm_reporting_<env>
      │ Synapse Link                         ┌─────────────────────────────────────────────┐
      ▼                                      │ bronze   cópia fiel das views (diário)      │
 Azure Synapse Serverless ──Lakehouse────────►│ silver   Power Query + colunas DAX + RLS    │
  rpt.vw_CRMReportDealPipeline  Federation   │ gold     views seguras (RLS por utilizador) │
  rpt.vw_InvestmentAllocation   (foreign     │ ref      stages, segmentos, lista de acessos│
  rpt.vw_CRMUserAccess           catalogs)   └──────────────────────┬──────────────────────┘
  rpt.vw_CRMLeads  (PRD e DEV)                                      │ SQL Warehouse
  crm.vAllUsers                                                     ▼ (identidade do utilizador)
 Excel lista de acessos ──► Volume ref.landing/rls      Databricks App (Streamlit)
```

Componentes no Databricks: 1 catálogo, 4 schemas, 1 volume, 2 connections + 2 foreign
catalogs, 1 SQL Warehouse, 1 Job (7 tarefas), 1 App, 2 grupos, 1–2 service principals.

### 0.2 Papéis necessários

| Papel | Quem | Para quê |
|---|---|---|
| **Implementador** (você) | equipa de dados | executa este guia |
| **Workspace admin** | plataforma | ativar Apps, criar warehouse, secrets |
| **Metastore / Account admin** | plataforma | criar catálogo, connections, grupos, service principals |
| **Admin do Synapse** | equipa Dataverse/Synapse | criar login SQL e abrir firewall |
| **Dono do negócio** | reporting | decidir Leads DEV vs PRD (A1), segmentos (A4), testes UAT |

### 0.3 Pedidos a fazer JÁ (demoram dias)

Copie e envie:

1. **Para o admin do Synapse** — *"Precisamos de um login SQL só de leitura no Synapse
   Serverless para o Databricks ler (1) `dynamicsynapseprod-ondemand.sql.azuresynapse.net`,
   base `dataverse_arrowcrm_org375adb08`: `rpt.vw_CRMReportDealPipeline`,
   `rpt.vw_InvestmentAllocation`, `rpt.vw_CRMUserAccess`, `rpt.vw_CRMLeads`, `crm.vAllUsers`;
   e (2) `dynamicsynapse-ondemand.sql.azuresynapse.net`, base
   `dataverse_arrowcrmdev_unq1b6f845c7703ee11a66d000d3a64d`: `rpt.vw_CRMLeads`.
   O login tem de conseguir ler o armazenamento por trás das views (credencial ao nível do
   servidor para o storage do Synapse Link). Precisamos também de liberar na firewall do
   Synapse o tráfego do Databricks serverless (vamos enviar os IPs/subnets)."*
   - Peça para testarem o login com SSMS/Azure Data Studio a fazer `SELECT TOP 10` de cada view.
2. **Para o admin da plataforma Databricks** — os itens das Fases 1 a 4 (pode enviar este documento).
3. **Para o negócio** — decisão sobre a origem dos Leads (A1) e grafia dos segmentos (A4),
   ver `00_Analise_PowerBI.md`. Até haver decisão, fica DEV (igual ao Power BI).

### 0.4 Checklist de saída da Fase 0
- [ ] Pedidos enviados
- [ ] Sabe o URL do workspace (ex.: `https://adb-1234567890123456.7.azuredatabricks.net`)
- [ ] Tem utilizador no workspace

---

<a id="fase-1"></a>
## Fase 1 — Verificar o workspace Databricks (workspace admin)

1. **Unity Catalog ativo**: no menu esquerdo clique **Catalog**. Se vê catálogos como
   `system` ou `main`, está ativo. Se não, o account admin tem de atribuir um metastore ao workspace.
2. **Serverless ativo**: menu **Compute → SQL warehouses → Create**: deve existir o tipo
   *Serverless*. Jobs serverless: em **Workflows/Jobs**, ao criar uma tarefa deve aparecer
   *Serverless* como compute.
3. **Databricks Apps ativo**: menu **Compute → Apps** (ou **+ New → App**). Se não existir,
   o workspace admin ativa em **Settings → Advanced / Previews** ("Databricks Apps").
4. **User authorization para Apps**: em **Settings → Previews** procure *"Databricks Apps
   - On-Behalf-Of User Authorization"* (o nome pode variar). Tem de estar **ON**. É o que
   permite a app consultar os dados com a identidade de cada utilizador, aplicando a RLS.
   - Se a sua organização não permitir, use o modo de recurso `AUTH_MODE=sp` (ver 6.9).

✅ Resultado: as quatro opções existem/estão ativas.

---

<a id="fase-2"></a>
## Fase 2 — Grupos e identidades (account admin)

### 2.1 Grupos
Em **Account Console** (`https://accounts.azuredatabricks.net`) → **User management → Groups → Add group**:

| Grupo | Membros |
|---|---|
| `crm_report_admins` | equipa de dados / donos do relatório (vêem tudo, gerem o projeto) |
| `crm_report_users` | todos os utilizadores do relatório (pode ser sincronizado do Entra ID) |

Depois, no workspace: **Settings → Identity and access → Groups → Add group** e adicione os dois.

> Os membros de `crm_report_admins` vêem **todos** os dados (como os membros do workspace
> Power BI). Os restantes só vêem o que a lista de acessos (RLS) permitir.

### 2.2 Service principal para produção
**Account Console → User management → Service principals → Add** → nome `sp-crm-reporting-prd`.
Adicione-o ao workspace (Settings → Identity and access → Service principals → Add).
Anote o **Application ID** (um GUID) — é usado no `databricks.yml` (`run_as`) e nos GRANTs.
Em DEV o job corre com o seu próprio utilizador.

> A **app** tem o seu próprio service principal criado automaticamente — não precisa de criar.

✅ Resultado: 2 grupos e 1 service principal visíveis no workspace.

---

<a id="fase-3"></a>
## Fase 3 — Catálogo, schemas e volume (metastore admin)

1. Abra **SQL Editor** (menu esquerdo).
2. Abra o ficheiro `sql/00_setup_admin.sql` deste projeto, copie o conteúdo para o editor.
3. Substitua **todas** as ocorrências de `${catalog}` por `crm_reporting_dev`
   (Ctrl+H no editor). Mais tarde repetirá com `crm_reporting_prd`.
4. Se o `CREATE CATALOG` der erro *"no storage root"*, use a variante com
   `MANAGED LOCATION` comentada no ficheiro (pede ao admin o URL da External Location).
5. Execute (**Run all**).
6. Dê-se permissões de trabalho no catálogo de DEV:
   ```sql
   GRANT ALL PRIVILEGES ON CATALOG crm_reporting_dev TO `o.seu.email@empresa.com`;
   ```

✅ Resultado: em **Catalog** aparece `crm_reporting_dev` com `bronze`, `silver`, `gold`, `ref`
e o volume `ref → Volumes → landing`.

---

<a id="fase-4"></a>
## Fase 4 — SQL Warehouse (workspace admin)

1. **Compute → SQL warehouses → Create SQL warehouse**
2. Nome `wh-crm-reporting`, Tipo **Serverless**, Tamanho **2X-Small** (dados pequenos),
   **Auto stop 10 min**, Scaling min 1 / max 2.
3. Create. Abra o warehouse → separador **Connection details** → copie o **ID** (está no
   *HTTP path* `/sql/1.0/warehouses/<ID>`).
4. **Permissions** do warehouse: `crm_report_users` = **Can use**; `crm_report_admins` = **Can manage**.
   > Em modo *user authorization* as queries correm com a identidade do utilizador final,
   > por isso **todos os utilizadores precisam de "Can use" no warehouse**.

✅ Resultado: warehouse em estado *Running/Stopped* e o ID anotado.

---

<a id="fase-5"></a>
## Fase 5 — Preparar o seu computador

### 5.1 Ferramentas
| Ferramenta | Como instalar | Verificar |
|---|---|---|
| Python 3.11+ | python.org | `python --version` |
| Git | git-scm.com | `git --version` |
| Databricks CLI (≥ 0.250) | Windows: `winget install Databricks.DatabricksCLI` · macOS: `brew tap databricks/tap && brew install databricks` · Linux: `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh \| sh` | `databricks --version` |
| VS Code (opcional) + extensão "Databricks" | marketplace | — |

### 5.2 Autenticar a CLI
```bash
databricks auth login --host https://adb-XXXXXXXXXXXXXXXX.X.azuredatabricks.net
# abre o browser; aceite. É criado um perfil em ~/.databrickscfg
databricks current-user me          # deve mostrar o seu e-mail
```

### 5.3 Obter o projeto e testar localmente (opcional mas recomendado — 10 min)
```bash
cd crm-performance-dbx
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python tools/generate_sample_data.py      # dados fictícios em sample_data/
python tools/build_demo_db.py             # corre o MESMO SQL do projeto em DuckDB
pytest -q tests/                          # testes (o de paridade é ignorado sem .parity/)
cd app
# Windows (PowerShell): $env:APP_BACKEND="duckdb"; streamlit run app.py
APP_BACKEND=duckdb streamlit run app.py   # abre http://localhost:8501
```
✅ Resultado: a app abre no browser com dados fictícios, utilizador `demo.user@example.com`.

### 5.4 Teste de paridade com os dados reais do PBIX (recomendado)
```bash
python tools/extract_pbix_reference.py "C:\caminho\CRM_Performance_Reporting_MVP_v1.pbix"
pytest -q tests/test_parity.py -s
```
✅ Resultado: todas as linhas `[OK ]` (44 colunas + RLS). A pasta `.parity/` contém dados
reais: **não a partilhe nem a coloque no Git** (já está no `.gitignore`).

### 5.5 Configurar o bundle
Edite `databricks.yml`, target `dev`:
- `workspace.host` → URL do workspace
- `variables.warehouse_id` → ID da Fase 4

```bash
databricks bundle validate -t dev
```
✅ Resultado: `Validation OK!`

---

<a id="fase-6"></a>
## Fase 6 — Primeiro deploy em DEV com dados de exemplo

### 6.1 Colocar a SUA conta na lista de acessos de exemplo
Edite `sample_data/rls/UserPlatformCountry.csv` e troque `demo.user@example.com` pelo
**seu e-mail do Databricks** (o que aparece em `databricks current-user me`).
Assim vê todos os dados (perfil `Central | All`). Também pode criar linhas para colegas
de teste com perfis restritos (ex.: `Atlas Capital` / `United Kingdom`).

### 6.2 Carregar os ficheiros para o volume
```bash
databricks fs cp -r sample_data/ dbfs:/Volumes/crm_reporting_dev/ref/landing/sample/ --overwrite
databricks fs cp sample_data/rls/UserPlatformCountry.csv dbfs:/Volumes/crm_reporting_dev/ref/landing/rls/UserPlatformCountry.csv --overwrite
databricks fs ls dbfs:/Volumes/crm_reporting_dev/ref/landing/sample/
```
(Alternativa pela UI: Catalog → crm_reporting_dev → ref → Volumes → landing → **Upload to this volume**.)

### 6.3 Deploy do bundle
```bash
databricks bundle deploy -t dev
```
✅ Resultado: em **Workflows/Jobs** aparece `[dev o_seu_nome] CRM Reporting - ETL diario`
e em **Compute → Apps** aparece `crm-performance-reporting` (prefixado em dev).

### 6.4 Correr o job
```bash
databricks bundle run crm_reporting_etl -t dev
```
Acompanhe em **Jobs → o job → Runs**. As 7 tarefas devem ficar verdes (~5–10 min na 1ª vez).
Se uma falhar, clique nela para ver o erro (ver Anexo A).

✅ Resultado: tarefa `validate` verde; em **Catalog** aparecem as tabelas silver e as views gold.
Confirme no SQL Editor:
```sql
SELECT terminal_snapshot, COUNT(*) FROM crm_reporting_dev.gold.vw_pipeline GROUP BY ALL;
SELECT * FROM crm_reporting_dev.ref.validation_log ORDER BY run_ts DESC;
```
O aviso `leads_active_source_match_pipeline = WARN` é **esperado** com Leads DEV (achado A1).

### 6.5 Permissões
Abra `sql/40_grants.sql` no SQL Editor, substitua `${catalog}` por `crm_reporting_dev`,
`<job-sp-application-id>` pelo seu e-mail (em dev o job corre consigo) e
`<app-sp-application-id>` pelo service principal da app
(**Compute → Apps → a app → Authorization/Overview → Service principal**, copie o *Application ID*).
Execute.

### 6.6 Iniciar a app
```bash
databricks bundle run crm_reporting_app -t dev
```
Ou pela UI: **Compute → Apps → a app → Start / Deploy**.

### 6.7 Confirmar a configuração da app (UI)
Em **Compute → Apps → a app → Edit**:
- **App resources**: `sql-warehouse` → o warehouse da Fase 4 → *Can use*.
- **User authorization → Scopes**: deve conter **`sql`** (adicione se não estiver; depois **Restart**).
- **Environment**: `CRM_CATALOG = crm_reporting_dev`, `AUTH_MODE = obo`.

### 6.8 Abrir a app
Clique no URL da app. Na primeira vez aparece um ecrã de **consentimento** ("A app quer
aceder em seu nome a SQL") → **Allow**. (Um admin pode dar consentimento por toda a organização.)

✅ Resultado: Home com KPIs; barra lateral mostra o seu e-mail; a secção **Administração**
aparece se for membro de `crm_report_admins`.

**Teste da RLS:** peça a um colega que esteja na lista de exemplo com perfil restrito
(e no grupo `crm_report_users`, sem ser admin) para abrir a app: deve ver apenas a sua
plataforma/país. Um utilizador fora da lista vê o aviso "Sem dados visíveis".

### 6.9 (Só se a user authorization NÃO puder ser ativada) Modo service principal
1. No `databricks.yml`, `app_auth_mode: sp` e remova `user_api_scopes` de `resources/crm_app.yml`.
2. Execute os GRANTs comentados "Só se AUTH_MODE=sp" de `40_grants.sql`.
3. `databricks bundle deploy -t dev && databricks bundle run crm_reporting_app -t dev`.
A app passa a aplicar a mesma regra RLS usando o e-mail que o Databricks envia no cabeçalho
`X-Forwarded-Email`. É seguro, mas a regra deixa de ser aplicada pelo Unity Catalog — o modo
`obo` é o preferido.

---

<a id="fase-7"></a>
## Fase 7 — Ligar ao Synapse (dados reais) — DEV e PRD

Pré-requisito: o login SQL da Fase 0 está criado e testado pelo admin do Synapse.

### 7.1 Rede
O compute **serverless** do Databricks tem de chegar a `*.sql.azuresynapse.net:1433`.
1. Workspace/account admin: **Account Console → Cloud resources → Network Connectivity
   Configurations (NCC)** → associe uma NCC ao workspace e copie os **IPs/subnets de saída
   estáveis** do serverless (ou crie *private endpoint rules* para o Synapse).
2. Admin do Synapse: adiciona esses IPs na **firewall do workspace Synapse**
   (Synapse workspace → Networking) — para o workspace PRD e para o DEV.

### 7.2 Secrets (credenciais do login SQL)
```bash
databricks secrets create-scope crm-reporting
databricks secrets put-secret crm-reporting synapse-user          # escreva o utilizador e Enter
databricks secrets put-secret crm-reporting synapse-password      # escreva a password
databricks secrets put-secret crm-reporting synapse-dev-user
databricks secrets put-secret crm-reporting synapse-dev-password
databricks secrets list-secrets crm-reporting
```
> Se DEV e PRD usarem o mesmo login, ponha os mesmos valores nas duas chaves.

### 7.3 Connections e foreign catalogs (metastore admin)
No SQL Editor execute `sql/02_federation_admin.sql` (substitua `<job-sp-application-id>`
pelo seu e-mail em DEV; em PRD pelo service principal). Alternativa pela UI:
**Catalog → + → Create a connection → Tipo SQLDW** e depois **Create catalog → Foreign**.

✅ Resultado: os `SELECT COUNT(*)` do passo 3 do ficheiro devolvem números (Pipeline ≈ 10 mil).
Se der *timeout* → rede (7.1). Se der *login failed* → secrets/login. Se der erro de
acesso ao storage → credencial do Synapse (voltar ao admin do Synapse).

### 7.4 Mudar o DEV para dados reais
No `databricks.yml`, target `dev`: `source_mode: federation`. Depois:
1. Carregue o **Excel real** da lista de acessos (`UserPlatformCountry 1.xlsx`, folha
   *Active Users Consuming Licenses*) para `/Volumes/crm_reporting_dev/ref/landing/rls/`
   e **apague o CSV de exemplo** dessa pasta (o job usa o ficheiro mais recente).
   > Confirme que o seu e-mail está no Excel (ou que é membro de `crm_report_admins`).
2. ```bash
   databricks bundle deploy -t dev
   databricks bundle run crm_reporting_etl -t dev
   ```
3. Na app: barra lateral → **Atualizar dados**.

✅ Resultado: validações `PASS` exceto o aviso esperado dos Leads DEV.

### 7.5 Leads DEV vs PRD (achado A1)
- Os **dois** são ingeridos sempre (tarefa `bronze`). Se a origem **inativa** falhar
  (ex.: sem acesso ao DEV), o job só regista um aviso.
- Para comparar: app → **Administração → Leads DEV vs PRD** (nº de leads, % de LeadIds que
  existem no pipeline, tempo médio no stage Lead).
- Para **mudar a origem ativa** quando o negócio decidir: `leads_source_active: PRD` no
  `databricks.yml` (ou no job: *Run now with different parameters*), `bundle deploy` e correr o job.
  Nada mais muda.

---

<a id="fase-8"></a>
## Fase 8 — Validação contra o Power BI (UAT)

Siga `03_Testes_UAT.md`. Resumo:
1. Atualize o Power BI e corra o job no mesmo dia.
2. Compare os números de referência (contagens por stage/estado, funil, quarters, KPIs).
3. Teste a RLS com 3 perfis: Central/All, All Portugal, uma plataforma+país.
4. Registe as diferenças. Diferenças esperadas e explicadas: grafias de segmentos (A4,
   se a fonte tiver os nomes corretos), Leads (A1, se mudar para PRD).

---

<a id="fase-9"></a>
## Fase 9 — Produção

1. **Fase 3** com `crm_reporting_prd`.
2. **Fase 7.3** com o service principal de produção nos GRANTs (e `GRANT READ` no scope:
   `databricks secrets put-acl crm-reporting <application-id-sp-prd> READ`).
3. Dê ao SP de produção acesso ao warehouse (*Can use*) e ao catálogo:
   `GRANT ALL PRIVILEGES ON CATALOG crm_reporting_prd TO \`<application-id-sp-prd>\`;`
4. Carregue o Excel da lista de acessos para `/Volumes/crm_reporting_prd/ref/landing/rls/`.
5. Edite o target `prod` em `databricks.yml` (host, warehouse_id, `run_as`).
6. Deploy (idealmente com o service principal, ex.: num pipeline Azure DevOps/GitHub Actions):
   ```bash
   databricks bundle validate -t prod
   databricks bundle deploy   -t prod
   databricks bundle run crm_reporting_etl -t prod
   databricks bundle run crm_reporting_app -t prod
   ```
7. `sql/40_grants.sql` com `crm_reporting_prd`.
8. Em **Jobs → o job → Edit**, configure **notificações de falha** (e-mail da equipa).
   O agendamento diário às 06:00 (Lisboa) fica ativo no target prod.
9. **Permissões da app**: já definidas no bundle (`crm_report_users` = Can use).
10. Partilhe o URL da app. Mantenha o Power BI em paralelo 2–4 semanas e depois desative o
    *scheduled refresh* e o acesso ao relatório antigo.

---

<a id="fase-10"></a>
## Fase 10 — Operação diária

| Tarefa | Como |
|---|---|
| **Dar/retirar acesso a um utilizador** | 1) adicionar/remover do grupo `crm_report_users`; 2) atualizar o Excel e carregá-lo para `ref/landing/rls/`; 3) correr o job (ou esperar pelo das 06:00). |
| **Ver se o refresh correu** | Jobs → Runs; ou na app, "Last Refresh" no cabeçalho; ou `ref.validation_log`. |
| **Refresh fora de horas** | Jobs → o job → **Run now**. Na app: **Atualizar dados**. |
| **Mudar a origem dos Leads** | parâmetro `leads_source_active` (7.5). |
| **Novo segmento / correção de grafia** | editar `sql/01_reference_data.sql` (`segment_mapping` e `dim_segment`) e `app/crm_app/metrics.py` (`SEGMENTS`), deploy + job. |
| **Excluir plataformas da página DMS Usage** | `ref.usage_excluded_platforms` em `01_reference_data.sql`. |
| **Alterar uma regra de negócio** | alterar o SQL/`metrics.py`, correr `pytest` (paridade!), deploy em dev, validar, deploy em prod. |
| **Custos** | warehouse serverless 2X-Small com auto-stop 10 min; job serverless ~5 min/dia; app: 1 instância. Ver *system.billing.usage*. |
| **Logs da app** | Compute → Apps → a app → **Logs**. |

---

<a id="anexo-a"></a>
## Anexo A — Resolução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `bundle validate`: *cannot resolve host* / *not authenticated* | CLI sem login | `databricks auth login --host …` |
| Job, tarefa `load_rls_access`: *Nenhum ficheiro RLS* | volume vazio | 6.2 / 7.4 |
| Job, tarefa `load_rls_access`: *Colunas em falta* | Excel com outra folha/cabeçalhos | a folha tem de se chamar *Active Users Consuming Licenses* com as colunas `(Do Not Modify) User`, `Full Name`, `Platform`, `Country`, `Primary Email` (ou use CSV) |
| Job, `bronze`: *Table or view not found: synapse_crm_prd…* | foreign catalog não criado / sem permissão | 7.3 e GRANT ao utilizador/SP do job |
| Job, `bronze`: timeout / *connection refused* | rede | 7.1 (NCC + firewall Synapse) |
| Job, `bronze`: *Falhou a ingestão dos Leads DEV, que é a origem ATIVA* | sem acesso ao Synapse DEV | resolver acesso, ou temporariamente `leads_source_active: PRD` |
| Job, `bronze`: *crm.vAllUsers indisponível* (aviso) | view não exposta | opcional; pedir acesso, ou carregar CSV para `bronze.crm_all_users` |
| Job, `silver_other_and_rls`: erro em `LoginsDone`/`ActiveCRMUser` | colunas diferentes em `crm.vAllUsers` | ajustar o bloco `silver.crm_users` em `21_silver_other.sql` |
| Job, `validate`: `bronze_fresh_today = FAIL` | ingestão não correu hoje | ver tarefa `bronze` |
| App: *Erro de autenticação … token do utilizador* | scope `sql` em falta ou preview desativado | 6.7 / Fase 1.4, depois **Restart** da app |
| App: *Não foi possível ler os dados… PERMISSION_DENIED* | faltam GRANTs ao utilizador | `40_grants.sql` (grupo `crm_report_users`) |
| App: *… warehouse … permission* | utilizador sem *Can use* no warehouse | Fase 4.4 |
| App abre mas "Sem dados visíveis" | e-mail não está na lista RLS (ou difere em maiúsculas/alias) | o e-mail tem de ser igual ao do login Databricks; atualizar Excel + job |
| App: alterações no Excel não aparecem | cache de 10 min | **Atualizar dados** na barra lateral |
| App: `CRM_CATALOG` errado após deploy pelo bundle | `app.yaml` vs `config` do bundle | o bundle (`resources/crm_app.yml` → `config.env`) prevalece; confirme em Compute → Apps → Environment |
| App não arranca, logs com erro de `pip` | versão de pacote indisponível | ajustar `app/requirements.txt` |

---

<a id="anexo-b"></a>
## Anexo B — Glossário Databricks (para quem vem do Power BI)

| Termo | Equivale a (Power BI) | Explicação |
|---|---|---|
| Unity Catalog (UC) | — | governação central: catálogos, permissões, linhagem |
| Catalog / Schema / Table / View | dataset / grupo / tabela | hierarquia `catalogo.schema.tabela` |
| Volume | pasta OneDrive/SharePoint | pasta gerida pelo UC para ficheiros |
| Lakehouse Federation / Foreign catalog | conector "SQL Server database" | consultar o Synapse sem copiar manualmente |
| Job (Lakeflow Jobs) | Scheduled refresh | execução agendada das tarefas de dados |
| SQL Warehouse | capacidade Power BI / motor VertiPaq | computação que executa as queries da app |
| Databricks App | relatório publicado no serviço | aplicação web alojada no Databricks |
| User authorization (OBO) | RLS com USERPRINCIPALNAME() | a app consulta como o utilizador → o UC aplica a segurança |
| Service principal | conta de serviço | identidade técnica para jobs e apps |
| Bundle (`databricks.yml`) | ficheiro .pbix + pipeline de deployment | definição versionada de jobs/apps, deploy por comando |
| `current_user()` | `USERPRINCIPALNAME()` | e-mail de quem está a consultar |
