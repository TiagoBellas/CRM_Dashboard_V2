"""
extract_pbix_reference.py

Extrai do ficheiro .pbix as tabelas importadas (INCLUINDO as colunas calculadas
DAX já materializadas) para a pasta .parity/ (ignorada pelo git).
Estes dados servem de "verdade" para o teste de paridade tests/test_parity.py,
que corre o SQL do projeto e compara coluna a coluna com o resultado do Power BI.

Uso:
    pip install pbixray pyarrow
    python tools/extract_pbix_reference.py caminho/para/CRM_Performance_Reporting_MVP_v1.pbix

ATENÇÃO: os ficheiros gerados contêm dados reais do CRM. Não os coloque no Git
nem os partilhe fora dos canais autorizados.
"""
from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / ".parity"
TABLES = [
    "Pipeline", "Leads", "Investment Allocation", "User Access Platform",
    "User_Access", "RLS_UserAccess_Raw", "_DimStage", "_DimSegment", "LastRefresh",
]


def main(pbix: str) -> None:
    from pbixray import PBIXRay

    OUT.mkdir(exist_ok=True)
    model = PBIXRay(pbix)
    for t in TABLES:
        df = model.get_table(t)
        path = OUT / f"{t.replace(' ', '_')}.parquet"
        df.to_parquet(path)
        print(f"{t:25s} {df.shape} -> {path}")
    (OUT / ".gitignore").write_text("*\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
