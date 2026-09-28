from __future__ import annotations
from functools import lru_cache
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from src.utils.config import get_settings

@lru_cache
def get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)

def schema_catalog() -> dict[str, list[str]]:
    insp = inspect(get_engine())
    return {table: [c["name"] for c in insp.get_columns(table)] for table in insp.get_table_names()}

def schema_text() -> str:
    cat = schema_catalog()
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in sorted(cat.items()))

def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    return pd.read_sql_query(text(sql), get_engine(), params=params or {})
