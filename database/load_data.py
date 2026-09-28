from __future__ import annotations
from pathlib import Path
import sys
ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH))
import pandas as pd
from sqlalchemy import create_engine, text
from src.utils.config import get_settings, ROOT

PROCESSED = ROOT / "data" / "processed"
TABLES = ["customers","subscription_plans","subscriptions","content","viewing_activity","payments","support_tickets","customer_feedback","churn_labels"]
DATE_COLS = {
    "customers":["registration_date"], "subscriptions":["subscription_start_date","subscription_end_date","cancellation_date"],
    "viewing_activity":["viewing_date"], "payments":["payment_date"], "support_tickets":["ticket_date"],
    "customer_feedback":["feedback_date"], "churn_labels":["churn_date"],
}

def main():
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    schema_sql = (ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        # psycopg2 can execute multi-statement DDL through exec_driver_sql.
        conn.exec_driver_sql(schema_sql)
        for table in reversed(TABLES):
            conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))

    for table in TABLES:
        df = pd.read_csv(PROCESSED / f"{table}.csv")
        for col in DATE_COLS.get(table, []):
            if col in df:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=2000)
        print(f"loaded {table}: {len(df):,}")

    # Optional model score mart when model training has already run.
    score_file = PROCESSED / "customer_churn_scores.csv"
    if score_file.exists():
        scores = pd.read_csv(score_file)
        scores.to_sql("ml_customer_scores", engine, if_exists="replace", index=False, method="multi", chunksize=2000)
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_ml_scores_customer ON ml_customer_scores(customer_id);")
        print(f"loaded ml_customer_scores: {len(scores):,}")

if __name__ == "__main__":
    main()
