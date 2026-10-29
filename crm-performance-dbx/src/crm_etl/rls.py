"""
Preparação da lista de acessos RLS (equivalente à query Power Query RLS_UserAccess_Raw):
  1. lê a folha "Active Users Consuming Licenses" do Excel (ou um CSV com as mesmas colunas)
  2. escolhe as colunas (Do Not Modify) User, Full Name, Platform, Country, Primary Email
  3. divide o país por "/" (1 linha por país) e faz trim
"""
from __future__ import annotations

import pandas as pd

SHEET = "Active Users Consuming Licenses"
SOURCE_COLS = {"(Do Not Modify) User": "user_id", "Full Name": "full_name", "Platform": "platform",
               "Country": "country", "Primary Email": "primary_email"}


def read_raw(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xlsm")):
        return pd.read_excel(path, sheet_name=SHEET, dtype=str)
    return pd.read_csv(path, dtype=str)


def transform(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.rename(columns=lambda c: str(c).strip())          # " Full Name" tem um espaço no Excel
    missing = [c for c in SOURCE_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f"Colunas em falta no ficheiro RLS: {missing}. Colunas lidas: {list(raw.columns)}")
    df = raw[list(SOURCE_COLS)].rename(columns=SOURCE_COLS)
    df["country"] = df["country"].fillna("").astype(str).str.split("/")
    df = df.explode("country")
    df["country"] = df["country"].str.strip().replace("", None)
    df = df.reset_index(drop=True).astype(object)
    return df.where(df.notna(), None)
