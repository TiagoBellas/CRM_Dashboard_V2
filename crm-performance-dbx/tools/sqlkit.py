"""
sqlkit.py - utilitários para executar os ficheiros sql/*.sql

* render()          substitui ${parametros}
* split_statements() divide um ficheiro em instruções (separador: ';' no fim da linha)
* to_duckdb()       traduz o dialeto Databricks SQL para DuckDB (usado apenas para
                    testes locais e para o modo DEMO da app; em produção o SQL corre
                    tal como está no Databricks).
"""
from __future__ import annotations

import re
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from crm_etl.sqltext import render, split_statements  # noqa: E402,F401


# --------------------------------------------------------------------------- #
# Tradução para DuckDB
# --------------------------------------------------------------------------- #
def _replace_function(sql: str, name: str, fn) -> str:
    """Substitui chamadas name(arg1, arg2, ...) respeitando parênteses/aspas."""
    out, i, low, n = [], 0, sql.lower(), len(name)
    while True:
        j = low.find(name.lower() + "(", i)
        if j == -1:
            out.append(sql[i:])
            break
        if j > 0 and (sql[j - 1].isalnum() or sql[j - 1] == "_"):
            out.append(sql[i : j + n + 1])
            i = j + n + 1
            continue
        out.append(sql[i:j])
        k, depth, args, cur, in_str = j + n + 1, 1, [], [], False
        while k < len(sql) and depth > 0:
            c = sql[k]
            if c == "'" :
                in_str = not in_str
            if not in_str:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                elif c == "," and depth == 1:
                    args.append("".join(cur))
                    cur = []
                    k += 1
                    continue
            cur.append(c)
            k += 1
        args.append("".join(cur))
        inner = [_replace_function(a, name, fn) for a in args]
        out.append(fn([a.strip() for a in inner]))
        i = k + 1
    return "".join(out)


def to_duckdb(sql: str, as_of_date: str | None = None) -> str:
    # blocos específicos de cada motor
    sql = re.sub(r"-- @dbx-only-begin.*?-- @dbx-only-end", "", sql, flags=re.S)
    sql = re.sub(r"^--duckdb: ?", "", sql, flags=re.M)
    # COMMENT 'xxx' entre o nome e o AS
    sql = re.sub(r"\n\s*COMMENT\s+'[^']*'\s*\n\s*AS\b", "\nAS", sql)
    # datas "agora"
    if as_of_date:
        sql = re.sub(r"current_date\(\)", f"DATE '{as_of_date}'", sql, flags=re.I)
    else:
        sql = re.sub(r"current_date\(\)", "current_date", sql, flags=re.I)
    sql = re.sub(r"current_timestamp\(\)", "current_timestamp", sql, flags=re.I)
    # datediff(end, start) -> date_diff('day', start, end)
    sql = _replace_function(sql, "datediff", lambda a: f"date_diff('day', {a[1]}, {a[0]})")
    # concat(...) do Spark devolve NULL se algum argumento for NULL -> usar ||
    sql = _replace_function(sql, "concat", lambda a: "(" + " || ".join(a) + ")")
    return sql
