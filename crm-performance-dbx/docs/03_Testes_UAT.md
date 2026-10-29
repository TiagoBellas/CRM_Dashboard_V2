# 03 — Testes e aceitação (UAT)

## 1. Testes automáticos (antes de cada deploy)

```bash
pip install -r requirements-dev.txt
pytest -q tests/
```

| Teste | O que garante | Estado na entrega |
|---|---|---|
| `tests/test_parity.py` | o SQL reproduz as 44 colunas calculadas DAX e a RLS do PBI, linha a linha, nos dados reais do `.pbix` (requer `tools/extract_pbix_reference.py`) | ✅ 44/44 colunas, 0 diferenças em 10.172 registos; RLS idêntica para 241 utilizadores |
| `tests/test_metrics.py` | medidas (funil cumulativo, KPIs, orçamento, quarters, matriz) com resultados conhecidos | ✅ 5/5 |
| Validações do job (`sql/90_validation.sql`) | correm todos os dias; o job falha em `FAIL` | ✅ testado em DuckDB |
| Teste das 11 páginas + 10 interações (Streamlit AppTest) | nenhuma página dá erro | ✅ (modo demo) |

## 2. Números de referência (snapshot do `.pbix`, refresh de 23/10/2026)

Use-os para comparar a app com o Power BI **no mesmo dia de dados**. Os da secção 2.1
vêm das colunas calculadas do PBIX (verdade do PBI). Os da 2.2 foram calculados pelas
funções da app sobre esses dados — confirme-os no Power BI (sem filtros, utilizador admin).

### 2.1 Contagens (filtro de relatório aplicado: abertos ou fechados no ano corrente)

| Indicador | Valor |
|---|---|
| Registos totais no modelo / visíveis no relatório | 10.172 / **8.451** |
| Leads / Deals visíveis | 3.192 / 5.259 |
| Status: Active / Lost / Won | 7.908 / 490 / 53 |
| Stage: 1. Lead / 2. Early Prospect / 3. NBO / 4. DD / 5. IC / 6. Won, Closing / 7. Won | 3.192 / 4.953 / 90 / 72 / 64 / 27 / 53 |
| Segmento: Other / Real-estate Equity / Real Estate Lending / Non-Performing / Single Name Credits / B&R / Secured Coll. | 5.299 / 2.665 / 195 / 132 / 73 / 59 / 28 |
| Valor total (Amount €) | ≈ € 116,37 B |

### 2.2 Medidas (página Deal Funnel, sem filtros)

| Medida PBI | Valor |
|---|---|
| Deals (contagem) | 8.451 |
| Conversion Rate % (Win Rate) | 0,6% |
| Lose Rate % | 3,6% |
| PP 2026 Budget | € 2,60 B |
| % PP 26 Achieved | 77,8% |
| Avg Deal Size | € 13,8 M |
| Avg Deal Age (Won only) | 195 days |
| Funil € — Lead / Early Prospect / NBO / DD / IC / Won, Closing / Won | € 116,37B (100%) / € 52,02B (44,7%) / € 10,00B (8,6%) / € 8,08B (6,9%) / € 4,75B (4,1%) / € 3,30B (2,8%) / € 2,01B (1,7%) |
| Drop-off € — Lead / EP / NBO / DD / IC | € 4,06B / € 5,40B / € 414,7M / € 223,9M / € 94,3M |
| Quarter Performance (Q4-2026 selecionado) — Leads: Current / Previous / LY | 1.926 / 243 / 225 |
| Quarter Performance (Q4-2026) — Deals: Current / Previous / LY | 257 / 773 / 245 |

> Os valores mudam a cada refresh. Para comparar noutra data, repita a extração do PBIX
> desse dia e calcule com `python tests/test_parity.py` + as funções de `metrics.py`.

## 3. Checklist UAT (negócio)

Marque cada linha como OK / NOK e anote diferenças.

**Dados**
- [ ] Contagens da secção 2.1 iguais (Home e Leads & Deals Table, sem filtros)
- [ ] Funil (montante e quantidade) igual ao PBI, com e sem filtro de plataforma
- [ ] Drop-off por stage igual
- [ ] Scorecard do funil (7 KPIs) igual
- [ ] Quarter Performance: os 4 cenários (Leads/Deals × Qtd/€), 2 quarters diferentes
- [ ] Pipeline Matrix: Segment × Stage e Platform × Segment × Stage
- [ ] Origination por Platform e por Country (contagem e €), filtro de ano
- [ ] New Leads by Segment: valores mensais e acumulado YTD
- [ ] DMS Usage: Licensed / Active / Login Rate do último mês
- [ ] Ligações "abrir" abrem o registo certo no CRM

**Segurança**
- [ ] Utilizador `Central | All` vê tudo
- [ ] Utilizador `All Portugal | Portugal` vê apenas Portugal
- [ ] Utilizador Plataforma + País vê apenas essa combinação (testar um com 2 países)
- [ ] Utilizador fora da lista não vê dados
- [ ] Utilizador sem ser admin não vê a página Administração nem consegue ler `gold.vw_pipeline_all` no SQL Editor

**Operação**
- [ ] Job agendado correu às 06:00 e "Last Refresh" mostra a hora certa
- [ ] Atualizar o Excel de acessos + correr o job reflete a alteração
- [ ] Falha simulada (ex.: renomear o ficheiro RLS) gera e-mail de notificação

**Decisões de negócio registadas**
- [ ] A1 — origem dos Leads: DEV ☐ / PRD ☐ (data / responsável: ________)
- [ ] A4 — grafia dos segmentos aceite ☐

## 4. Diferenças esperadas face ao PBI
| Situação | Diferença | Motivo |
|---|---|---|
| Fonte passa a ter segmentos com grafia correta | menos "Other" | A4 (correção) |
| `leads_source_active = PRD` | "Tempo médio no stage Lead" passa a ter valor | A1 (no PBI é sempre vazio) |
| Página DMS Usage, lista de utilizadores | dados atuais em vez de estáticos | A3 |
| Medida `PP 2026 Budget` em anos seguintes | usa o ano corrente (o nome do PBI fixava 2026) | o DAX já usava `YEAR(TODAY())` |
