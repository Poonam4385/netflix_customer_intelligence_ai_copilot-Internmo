from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
MODELS.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

DROP_ALWAYS = {
    "customer_id", "first_name", "last_name", "state_or_region",
    "registration_date", "churn_date", "churn_reason", "anchor_date",
    "last_view_date", "last_failed_payment_date", "current_subscription_status",
}

CATEGORICAL_FEATURES = [
    "gender", "country", "acquisition_channel", "customer_segment", "preferred_language",
    "current_plan", "current_plan_id", "auto_renew",
]


def load_features() -> pd.DataFrame:
    return pd.read_csv(DATA / "customer_features.csv")


def model_columns(df: pd.DataFrame, target: str, extra_drop: set[str] | None = None):
    drop = set(DROP_ALWAYS) | {target}
    if extra_drop:
        drop |= set(extra_drop)
    cols = [c for c in df.columns if c not in drop]
    cats = [c for c in CATEGORICAL_FEATURES if c in cols]
    nums = [c for c in cols if c not in cats and pd.api.types.is_numeric_dtype(df[c])]
    return nums, cats


def make_preprocessor(numeric: list[str], categorical: list[str], scale_numeric: bool = False):
    num_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        num_steps.append(("scaler", StandardScaler()))
    num_pipe = Pipeline(num_steps)
    cat_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
    ])
    return ColumnTransformer([
        ("num", num_pipe, numeric),
        ("cat", cat_pipe, categorical),
    ], remainder="drop")


def write_json(path: Path, payload: dict):
    def default(x):
        if isinstance(x, (np.integer,)): return int(x)
        if isinstance(x, (np.floating,)): return float(x)
        if isinstance(x, np.ndarray): return x.tolist()
        raise TypeError(type(x).__name__)
    path.write_text(json.dumps(payload, indent=2, default=default), encoding="utf-8")
