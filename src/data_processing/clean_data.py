from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

COUNTRY_MAP = {
    "us":"United States","usa":"United States","u.s.a":"United States","united states":"United States",
    "uk":"United Kingdom","u.k.":"United Kingdom","britain":"United Kingdom","united kingdom":"United Kingdom",
    "in":"India","india":"India","bharat":"India",
    "uae":"United Arab Emirates","u.a.e":"United Arab Emirates","united arab emirates":"United Arab Emirates",
    "ca":"Canada","canada":"Canada","au":"Australia","australia":"Australia",
    "de":"Germany","germany":"Germany","fr":"France","france":"France",
    "es":"Spain","spain":"Spain","it":"Italy","italy":"Italy",
    "jp":"Japan","japan":"Japan","kr":"South Korea","s. korea":"South Korea","south korea":"South Korea",
    "mx":"Mexico","mexico":"Mexico","br":"Brazil","brazil":"Brazil",
    "ar":"Argentina","argentina":"Argentina","za":"South Africa","south africa":"South Africa",
    "ng":"Nigeria","nigeria":"Nigeria","ph":"Philippines","philippines":"Philippines",
    "id":"Indonesia","indonesia":"Indonesia","pl":"Poland","poland":"Poland",
}
DEVICE_MAP = {
    "mobile":"Mobile","phone":"Mobile","smartphone":"Mobile","tablet":"Tablet","ipad":"Tablet",
    "laptop":"Laptop","desktop":"Laptop","pc":"Laptop",
    "smart tv":"Smart TV","smarttv":"Smart TV","tv":"Smart TV",
    "gaming console":"Gaming Console","console":"Gaming Console","playstation/xbox":"Gaming Console",
}

DATE_COLUMNS = {
    "customers": ["registration_date"],
    "subscriptions": ["subscription_start_date", "subscription_end_date", "cancellation_date"],
    "viewing_activity": ["viewing_date"],
    "payments": ["payment_date"],
    "support_tickets": ["ticket_date"],
    "customer_feedback": ["feedback_date"],
    "churn_labels": ["churn_date"],
}


def canonical_country(value):
    if pd.isna(value):
        return np.nan
    key = str(value).strip().lower()
    return COUNTRY_MAP.get(key, str(value).strip().title())


def canonical_device(value):
    if pd.isna(value):
        return "Unknown"
    key = str(value).strip().lower()
    return DEVICE_MAP.get(key, str(value).strip().title())


def load_raw() -> dict[str, pd.DataFrame]:
    names = [
        "customers", "subscription_plans", "subscriptions", "content", "viewing_activity",
        "payments", "support_tickets", "customer_feedback", "churn_labels"
    ]
    return {name: pd.read_csv(RAW / f"{name}.csv") for name in names}


def _format_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def reconcile_payment_subscriptions(payments: pd.DataFrame, subscriptions: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Resolve each payment to the subscription segment active on payment_date.

    Segments are treated as half-open intervals [start, next_start). This removes ambiguity
    on plan-change dates, where one segment ends on the same day the next begins.
    """
    subs = subscriptions.sort_values(["customer_id", "subscription_start_date", "subscription_id"]).copy()
    subs["next_start"] = subs.groupby("customer_id")["subscription_start_date"].shift(-1)
    far_future = pd.Timestamp("2100-01-01")
    terminal_end = subs["cancellation_date"].fillna(subs["subscription_end_date"])
    subs["end_exclusive"] = subs["next_start"].fillna(terminal_end + pd.Timedelta(days=1)).fillna(far_future)

    candidates = payments.drop(columns=["subscription_id"], errors="ignore").merge(
        subs[["customer_id", "subscription_id", "subscription_start_date", "end_exclusive"]],
        on="customer_id", how="left"
    )
    valid = candidates[
        (candidates["payment_date"] >= candidates["subscription_start_date"]) &
        (candidates["payment_date"] < candidates["end_exclusive"])
    ].copy()
    valid = valid.sort_values(["payment_id", "subscription_start_date"], ascending=[True, False])
    valid = valid.drop_duplicates("payment_id", keep="first")

    resolved = payments.drop(columns=["subscription_id"], errors="ignore").merge(
        valid[["payment_id", "subscription_id"]], on="payment_id", how="left"
    )

    # Some synthetic billing rows occur after the recorded cancellation date. For referential
    # completeness, attach these to the most recently started subscription for that customer.
    # They remain identifiable analytically because payment_date > cancellation_date.
    missing = resolved["subscription_id"].isna()
    if missing.any():
        fallback_candidates = resolved.loc[missing, ["payment_id", "customer_id", "payment_date"]].merge(
            subs[["customer_id", "subscription_id", "subscription_start_date"]], on="customer_id", how="left"
        )
        fallback_candidates = fallback_candidates[
            fallback_candidates["subscription_start_date"] <= fallback_candidates["payment_date"]
        ].sort_values(["payment_id", "subscription_start_date"], ascending=[True, False])
        fallback = fallback_candidates.drop_duplicates("payment_id")[["payment_id", "subscription_id"]]
        fallback_map = fallback.set_index("payment_id")["subscription_id"]
        resolved.loc[missing, "subscription_id"] = resolved.loc[missing, "payment_id"].map(fallback_map)

    unresolved = int(resolved["subscription_id"].isna().sum())
    return resolved, unresolved


def clean_all() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    d = load_raw()
    report: dict[str, object] = {}

    # Customers
    c = d["customers"].copy()
    report["customer_duplicate_rows_removed"] = int(c.duplicated("customer_id").sum())
    c = c.drop_duplicates("customer_id", keep="first").copy()
    c["country"] = c["country"].map(canonical_country).fillna("Unknown")
    invalid_age = c["age"].notna() & ~c["age"].between(13, 100)
    report["invalid_age_rows"] = int(invalid_age.sum())
    c.loc[invalid_age, "age"] = np.nan
    country_medians = c.groupby("country")["age"].transform("median")
    c["age"] = c["age"].fillna(country_medians).fillna(c["age"].median()).round().astype("Int64")
    c["city"] = c["city"].fillna("Unknown")
    lang_mode = c["preferred_language"].mode(dropna=True)
    c["preferred_language"] = c["preferred_language"].fillna(lang_mode.iloc[0] if len(lang_mode) else "English")
    c = _format_dates(c, DATE_COLUMNS["customers"])
    d["customers"] = c

    # Standard date parsing
    for name in ["subscriptions", "viewing_activity", "payments", "support_tickets", "customer_feedback", "churn_labels"]:
        d[name] = _format_dates(d[name].copy(), DATE_COLUMNS[name])

    # Viewing: canonical categories, median imputation for completion. Preserve extreme binge sessions.
    v = d["viewing_activity"].copy()
    v["device_type"] = v["device_type"].map(canonical_device)
    v["login_location"] = v["login_location"].map(canonical_country).fillna("Unknown")
    content_median = v.groupby("content_id")["completion_percentage"].transform("median")
    v["completion_percentage"] = v["completion_percentage"].fillna(content_median).fillna(v["completion_percentage"].median())
    report["watch_duration_p995"] = float(v["watch_duration_minutes"].quantile(.995))
    report["session_duration_p995"] = float(v["session_duration_minutes"].quantile(.995))
    d["viewing_activity"] = v

    # Tickets: impossible dates become NULL, while the ticket text/metadata are retained.
    t_raw = pd.read_csv(RAW / "support_tickets.csv")
    invalid_ticket_dates = pd.to_datetime(t_raw["ticket_date"], errors="coerce").isna()
    report["invalid_ticket_dates_to_null"] = int(invalid_ticket_dates.sum())
    t = d["support_tickets"].copy()
    # Missing resolution/CSAT are expected for open tickets. Do not fake satisfaction values in the DB.
    d["support_tickets"] = t

    # Feedback: keep supplied sentiment_label for auditability; derive corrected sentiment downstream when needed.
    fb = d["customer_feedback"].copy()
    rating_sentiment = np.select([fb["rating"] <= 2, fb["rating"] >= 4], ["Negative", "Positive"], default="Neutral")
    report["feedback_rating_label_disagreements"] = int((fb["sentiment_label"] != rating_sentiment).sum())
    d["customer_feedback"] = fb

    # Subscription price/plan mismatches are concentrated in Plan Changed history rows; preserve source semantics and audit them.
    s = d["subscriptions"].copy()
    plans = d["subscription_plans"][["plan_id", "monthly_price"]].rename(columns={"monthly_price": "catalog_price"})
    sm = s.merge(plans, on="plan_id", how="left")
    report["subscription_plan_price_mismatch_rows"] = int((sm["monthly_price"].round(2) != sm["catalog_price"].round(2)).sum())
    d["subscriptions"] = s

    # Payments: keep anomalous amounts in the clean fact table; feature/model code uses robust transformations.
    p = d["payments"].copy()
    report["payment_amount_p995"] = float(p["amount"].quantile(.995))
    p, unresolved = reconcile_payment_subscriptions(p, s)
    report["payments_unresolved_subscription_id"] = unresolved
    d["payments"] = p

    # Integrity audit
    customer_ids = set(c["customer_id"])
    report["orphan_customer_fk_counts"] = {
        name: int((~df["customer_id"].isin(customer_ids)).sum())
        for name, df in d.items() if "customer_id" in df.columns and name != "customers"
    }
    report["row_counts"] = {k: int(len(v)) for k, v in d.items()}

    # Save ISO date strings for portable CSV loading.
    for name, df in d.items():
        out = df.copy()
        for col in DATE_COLUMNS.get(name, []):
            if col in out.columns and pd.api.types.is_datetime64_any_dtype(out[col]):
                out[col] = out[col].dt.strftime("%Y-%m-%d")
        out.to_csv(OUT / f"{name}.csv", index=False)

    (OUT / "cleaning_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return d


if __name__ == "__main__":
    clean_all()
    print(f"Cleaned files written to {OUT}")
