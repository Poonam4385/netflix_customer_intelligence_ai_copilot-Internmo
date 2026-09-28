from __future__ import annotations
import json, re, time
from pathlib import Path
import pandas as pd
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from src.llm.client import LLMClient
from src.database.db import get_engine, schema_catalog, schema_text
from src.utils.config import get_settings, ROOT

BLOCKED_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Merge, exp.Command)
AUDIT = ROOT / "logs" / "sql_audit.jsonl"

def _strip_fence(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";")

def validate_sql(sql: str, catalog: dict[str, list[str]] | None = None) -> str:
    sql = _strip_fence(sql)
    statements = sqlglot.parse(sql, read="postgres")
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is allowed")
    tree = statements[0]
    if any(tree.find(node) is not None for node in BLOCKED_NODES):
        raise ValueError("Only read-only SELECT queries are allowed")
    # sqlglot SELECT/UNION/subquery queries contain at least one Select; non-query commands do not.
    if tree.find(exp.Select) is None:
        raise ValueError("Only SELECT/CTE queries are allowed")
    catalog = catalog or schema_catalog()
    allowed_tables = set(catalog)
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    refs = {t.name for t in tree.find_all(exp.Table) if t.name not in cte_names}
    unknown = refs - allowed_tables
    if unknown:
        raise ValueError(f"Unknown/disallowed tables: {sorted(unknown)}")
    # Validate qualified columns and conservative unqualified columns.
    aliases = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
    for col in tree.find_all(exp.Column):
        if col.name == "*":
            continue
        if col.table:
            base = aliases.get(col.table, col.table)
            if base in catalog and col.name not in catalog[base]:
                raise ValueError(f"Unknown column {col.table}.{col.name}")
            # Columns qualified by a CTE/subquery alias are validated by PostgreSQL at execution.
        elif refs and not any(col.name in catalog[t] for t in refs):
            # Allow select aliases referenced in ORDER BY/GROUP BY.
            aliases_out = {a.alias for a in tree.find_all(exp.Alias) if a.alias}
            if col.name not in aliases_out:
                raise ValueError(f"Unknown column {col.name}")
    return sql

def execute_safe(sql: str) -> pd.DataFrame:
    s = get_settings()
    safe = validate_sql(sql)
    wrapped = f"SELECT * FROM ({safe}) AS _safe_query LIMIT {int(s.sql_row_limit)}"
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL statement_timeout = {int(s.sql_timeout_ms)}"))
        return pd.read_sql_query(text(wrapped), conn)

def ask(question: str) -> dict:
    llm = LLMClient()
    schema = schema_text()
    system = """You generate PostgreSQL for a read-only analytics database. Return SQL only, no markdown.\nRules: use only supplied schema; SELECT/CTEs only; never write data; prefer explicit joins; use dataset MAX(date) instead of CURRENT_DATE when the data is historical; avoid SELECT * unless necessary."""
    prompt = f"SCHEMA:\n{schema}\n\nQUESTION:\n{question}\n\nReturn one PostgreSQL SELECT query."
    started = time.time(); status="ok"; error=None; sql=""; rows=0
    try:
        sql = validate_sql(llm.generate(prompt, system, 1200))
        df = execute_safe(sql); rows=len(df)
        result_csv = df.head(100).to_csv(index=False)
        answer = llm.generate(
            f"Question: {question}\nSQL: {sql}\nResult rows ({rows} total, first up to 100):\n{result_csv}\nExplain only what the result supports. Do not invent numbers.",
            "You are a business analytics interpreter. Be concise, distinguish facts from interpretation, and never invent data.", 1000
        )
        return {"question":question,"sql":sql,"data":df,"answer":answer}
    except Exception as e:
        status="error"; error=str(e); raise
    finally:
        AUDIT.parent.mkdir(exist_ok=True)
        with AUDIT.open("a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":time.time(),"question":question,"sql":sql,"status":status,"rows":rows,"error":error,"elapsed_s":round(time.time()-started,3)})+"\n")
