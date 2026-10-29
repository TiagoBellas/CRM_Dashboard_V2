"""
generate_sample_data.py - gera dados SINTÉTICOS (fictícios) com a mesma estrutura das
views do Synapse, para:
  * testar o pipeline no Databricks antes de existir acesso ao Synapse (source_mode=sample)
  * correr a app localmente em modo DEMO

Nenhum dado real é usado. Plataformas, pessoas e e-mails são inventados.
Uso:  python tools/generate_sample_data.py [--rows 3000] [--seed 42]
Gera: sample_data/*.csv  e  sample_data/rls/UserPlatformCountry.csv
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "sample_data"

PLATFORMS = [  # nome na fonte (com sufixos societários, como no CRM), país(es)
    ("Atlas Capital Ltd", ["United Kingdom", "Ireland"]),
    ("Boreal Finance SpA", ["Italy"]),
    ("Cobalt Real Estate BV", ["Netherlands", "Germany"]),
    ("Delta Credit, Lda", ["Portugal"]),
    ("Ember Servicing, SA", ["Spain", "Portugal"]),
    ("Fjord Lending", ["Germany"]),
    ("Granite Partners Ltd", ["United Kingdom"]),
    ("Helix Investimenti SpA", ["Italy", "France"]),
]
SEGMENTS = ["Real Estate Lending", "Opportunistic Credit", "Non-Performing", "Bankruptcies and restructuring",
            "Single Name Credits", "Secured Collaterals & Value-add", "Real-estate Equity",
            "Investment Grade Asset-Backed", "Unknown Strategy"]
SEG_P = [.12, .06, .06, .04, .05, .04, .35, .03, .25]
VERTICALS = ["Bridge", "Real Estate", "Credit", "Development"]
FIRST = ["Ana", "Bruno", "Carla", "David", "Eva", "Filipe", "Grace", "Hugo", "Ines", "John", "Kate", "Luis",
         "Marta", "Nuno", "Olga", "Paulo", "Rita", "Sam", "Tiago", "Vera"]
LAST = ["Silva", "Smith", "Rossi", "Costa", "Muller", "Garcia", "Brown", "Santos", "Bianchi", "Murphy"]
STAGES_DEAL = ["Early Prospect", "NBO / Preliminary Bids", "In Due Diligence", "IC Approved", "Won, Closing"]


def person(rng) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def gen_pipeline(rng, n: int, today: datetime) -> pd.DataFrame:
    rows = []
    start = today - timedelta(days=int(365 * 2.7))
    originators = [person(rng) for _ in range(30)]
    mds = [person(rng) for _ in range(6)]
    for _ in range(n):
        plat, countries = PLATFORMS[rng.integers(len(PLATFORMS))]
        is_lead = rng.random() < 0.32
        created = min(today - timedelta(minutes=5),
                      start + timedelta(days=float(rng.uniform(0, (today - start).days)), hours=float(rng.uniform(8, 18))))
        seg = rng.choice(SEGMENTS, p=SEG_P)
        r = dict(
            RecordType="Lead" if is_lead else "Deal", RecordId=str(uuid.uuid4()).upper(),
            DealId=None, LeadId=None,
            SourceSystem="CRM" if is_lead else rng.choice(["CRM", "SLS", "MCP"], p=[.45, .38, .17]),
            EntityName=None, Name=f"{'Lead' if is_lead else 'Deal'} {rng.choice(['Project', 'Portfolio', 'Asset', 'Loan'])} "
                                  f"{rng.integers(1000, 9999)}",
            CreatedOn=created, ModifiedOn=None, ClosedOn=None,
            PassedToNBO=None, PassedToDD=None, PassedToIC=None, PassedToWon=None,
            StateName="Active", StatusName="Active", ActiveStage=None, LastDealStatus=None, ClosureReason=None,
            Segment=f"{rng.choice(['Equity', 'Credit', 'Mixed'])} - {seg}" if rng.random() > .05 else None,
            Platform=plat, Template=rng.choice(VERTICALS), CentralMD=rng.choice(mds),
            FundName=rng.choice(["Fund I", "Fund II", "Fund III", None], p=[.3, .3, .2, .2]),
            CountryName=rng.choice(countries) if rng.random() > .02 else None,
            OriginatorName=rng.choice(originators), Seller=rng.choice(["Bank A", "Bank B", "Servicer C", "Private"]),
            OwnerName=person(rng), CurrencyName=rng.choice(["EUR", "GBP"], p=[.6, .4]), LeadStatus=None,
            DescriptionText="Synthetic record for testing", PlatformId=str(uuid.uuid5(uuid.NAMESPACE_DNS, plat)),
        )
        amount = float(np.round(rng.lognormal(16.5, 1.3), -3)) if rng.random() > .3 else None
        r["AmountInEuro"] = amount
        r["ExchangeRate"] = 1.0 if r["CurrencyName"] == "EUR" else 1.17
        r["AmountBase"] = None if amount is None else round(amount / r["ExchangeRate"], 2)
        age = (today - created).days
        if is_lead:
            r["LeadId"] = "{" + str(uuid.uuid4()).upper() + "}"
            r["EntityName"] = "arrow_lead"
            r["ActiveStage"] = "Lead"
            st = rng.choice(["Killed", "Early Lead", "Rejected", "On Hold", "Advanced Lead", "Approved"],
                            p=[.55, .15, .1, .08, .07, .05])
            r["LeadStatus"] = st
            if st in ("Killed", "Rejected", "Approved") and rng.random() < .8:
                r["ClosedOn"] = created + timedelta(days=float(rng.uniform(5, max(6, age))))
        else:
            r["DealId"] = "{" + str(uuid.uuid4()).upper() + "}"
            r["EntityName"] = {"CRM": "opportunity", "SLS": "arrow_loandeal", "MCP": "arrow_mcploandeals"}[r["SourceSystem"]]
            outcome = rng.choice(["open", "won", "lost"], p=[.68, .12, .20])
            reached = int(rng.choice(range(5), p=[.70, .12, .08, .06, .04]))
            t = created
            for i, col in enumerate(["PassedToNBO", "PassedToDD", "PassedToIC", "PassedToWon"]):
                if reached > i or outcome == "won":
                    t = t + timedelta(days=float(rng.uniform(10, 90)))
                    if t < today:
                        r[col] = t
            if outcome == "open":
                r["ActiveStage"] = STAGES_DEAL[reached]
            elif outcome == "won":
                r["ActiveStage"] = rng.choice(["Won", "Closed"])  # a fonte usa "Closed" (o PQ troca para Won)
                r["StateName"] = "Won" if r["SourceSystem"] == "CRM" else "Active"
                r["ClosedOn"] = min(today, (r["PassedToWon"] or created) + timedelta(days=float(rng.uniform(5, 60))))
            else:
                r["ActiveStage"] = "Lost" if rng.random() > .1 else "Early Prospect"   # 10% gera alertas DQ
                r["StateName"] = "Lost" if rng.random() > .25 else "Active"
                last = STAGES_DEAL[reached]
                r["LastDealStatus"] = "NBO Stage" if last == "NBO / Preliminary Bids" and rng.random() < .3 else last
                if rng.random() < .1:
                    r["LastDealStatus"] = None
                r["ClosureReason"] = rng.choice(["Price", "Competition", "Did not Trade", None], p=[.35, .3, .2, .15])
                r["ClosedOn"] = min(today, created + timedelta(days=float(rng.uniform(20, max(21, age)))))
        r["ModifiedOn"] = r["ClosedOn"] or min(today, created + timedelta(days=float(rng.uniform(0, max(1, age)))))
        rows.append(r)
    return pd.DataFrame(rows)


def gen_leads(pipe: pd.DataFrame, rng, today: datetime) -> pd.DataFrame:
    """Leads PRD: os mesmos LeadId do pipeline. Leads DEV: ids diferentes (como no PBI real)."""
    lp = pipe[pipe["RecordType"] == "Lead"].copy()
    prd = lp.copy()
    prd["_source_env"] = "PRD"
    dev = lp.sample(frac=.9, random_state=1).copy()
    dev["LeadId"] = ["{" + str(uuid.uuid4()).upper() + "}" for _ in range(len(dev))]
    dev["RecordId"] = [str(uuid.uuid4()).upper() for _ in range(len(dev))]
    dev["LeadStatus"] = rng.choice(["Rejected", "Early Lead", "Approved", "On Hold"], size=len(dev))
    dev["ClosedOn"] = None
    dev["_source_env"] = "DEV"
    cols = ["RecordType", "RecordId", "DealId", "LeadId", "SourceSystem", "EntityName", "Name", "CreatedOn",
            "ModifiedOn", "ClosedOn", "StateName", "StatusName", "ActiveStage", "LeadStatus", "ClosureReason",
            "Segment", "Platform", "Template", "CentralMD", "FundName", "CountryName", "OriginatorName", "Seller",
            "OwnerName", "AmountBase", "CurrencyName", "LastDealStatus", "ExchangeRate", "AmountInEuro",
            "PassedToNBO", "PassedToDD", "PassedToIC", "PassedToWon", "DescriptionText", "_source_env"]
    out = pd.concat([prd, dev])[cols]
    out["Segment"] = out["Segment"].str.split(" - ").str[-1]
    return out


def main(n: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    today = datetime.now().replace(microsecond=0)
    OUT.mkdir(exist_ok=True)
    (OUT / "rls").mkdir(exist_ok=True)
    pipe = gen_pipeline(rng, n, today)
    pipe.to_csv(OUT / "crm_deal_pipeline.csv", index=False)
    gen_leads(pipe, rng, today).to_csv(OUT / "crm_leads.csv", index=False)

    ia = []
    for plat, countries in PLATFORMS:
        for c in countries:
            ia.append(dict(InvestmentAllocationId=str(uuid.uuid4()), Platform=plat, CountryName=c,
                           Year=today.year, BudgetBase=float(rng.integers(2, 40)) * 10_000_000,
                           PlatformId=str(uuid.uuid5(uuid.NAMESPACE_DNS, plat))))
    pd.DataFrame(ia).to_csv(OUT / "investment_allocation.csv", index=False)

    ua = []
    months = pd.date_range(end=pd.Timestamp(today).to_period("M").to_timestamp(), periods=12, freq="MS")
    for plat, _ in PLATFORMS + [("Development", []), ("Service Account", [])]:
        lic = int(rng.integers(3, 40))
        for ms in months:
            act = int(rng.integers(0, lic + 1))
            ua.append(dict(SourceSystem="CRM", EntityName="UserAccess12M", Platform=plat.split(" ")[0],
                           MonthStart=ms, MonthKey=ms.year * 100 + ms.month, LicensedUsers=lic, ActiveUsers=act,
                           AccessRecords=act * int(rng.integers(1, 30)), LastAccessInMonthUtc=ms + timedelta(days=20),
                           LoginRatePct=round(act / lic, 4)))
    pd.DataFrame(ua).to_csv(OUT / "crm_user_access_platform.csv", index=False)

    users = []
    for i in range(120):
        ll = None if rng.random() < .3 else (today - timedelta(days=float(rng.uniform(0, 200)))).date()
        users.append(dict(UserID=str(uuid.uuid4()), UserName=person(rng), Title=rng.choice(["Analyst", "Director", "NULL"]),
                          BusinessUnit=rng.choice([p.split(" ")[0] for p, _ in PLATFORMS] + ["Central"]),
                          LastLogin=str(ll) if ll else "-", LoginsDone=int(rng.integers(0, 300)), ActiveCRMUser="Yes"))
    pd.DataFrame(users).to_csv(OUT / "crm_all_users.csv", index=False)

    # Lista RLS no MESMO formato do Excel "UserPlatformCountry.xlsx" (folha Active Users Consuming Licenses)
    rls = [("demo.user@example.com", "Central", "All"),
           ("ana.portugal@example.com", "All Portugal", "Portugal"),
           ("bruno.atlas@example.com", "Atlas Capital", "United Kingdom / Ireland"),
           ("carla.boreal@example.com", "Boreal Finance", "Italy"),
           ("david.cobalt@example.com", "Cobalt Real Estate", "Netherlands")]
    pd.DataFrame([{"(Do Not Modify) User": str(uuid.uuid4()), "(Do Not Modify) Row Checksum": "x",
                   "(Do Not Modify) Modified On": today, " Full Name": e.split("@")[0].replace(".", " ").title(),
                   "Platform": p, "Country": c, "Primary Email": e} for e, p, c in rls]
                 ).to_csv(OUT / "rls" / "UserPlatformCountry.csv", index=False)
    print(f"Gerados {len(pipe)} registos de pipeline em {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    main(a.rows, a.seed)
