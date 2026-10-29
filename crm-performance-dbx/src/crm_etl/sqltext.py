"""Leitura de ficheiros .sql: substituição de ${parametros} e divisão em instruções."""
from __future__ import annotations

import re


def render(sql: str, params: dict) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in params:
            raise KeyError(f"Parâmetro em falta no ficheiro SQL: ${{{key}}}")
        return str(params[key])

    return re.sub(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}", repl, sql)


def _has_code(stmt: str) -> bool:
    return any(l.strip() and not l.strip().startswith("--") for l in stmt.splitlines())


def split_statements(sql: str) -> list[str]:
    """Divide por ';' no fim de linha (os ficheiros do projeto seguem esta convenção)."""
    stmts, buf = [], []
    for line in sql.splitlines():
        buf.append(line)
        if line.rstrip().endswith(";") and not line.lstrip().startswith("--"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if _has_code(stmt):
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if _has_code(tail):
        stmts.append(tail)
    return stmts


def strip_engine_blocks(sql: str) -> str:
    """No Databricks: remove os blocos '-- @duckdb-only' (são só comentários, por segurança)."""
    return re.sub(r"-- @duckdb-only-begin.*?-- @duckdb-only-end", "", sql, flags=re.S)
