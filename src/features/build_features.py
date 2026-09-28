from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed"

DATE_COLS = {
    "customers": ["registration_date"], "subscriptions": ["subscription_start_date", "subscription_end_date", "cancellation_date"],
    "viewing_activity": ["viewing_date"], "payments": ["payment_date"], "support_tickets": ["ticket_date"],
    "customer_feedback": ["feedback_date"], "churn_labels": ["churn_date"],
}


def load_processed() -> dict[str, pd.DataFrame]:
    names = ["customers","subscription_plans","subscriptions","content","viewing_activity","payments","support_tickets","customer_feedback","churn_labels"]
    out = {}
    for name in names:
        df = pd.read_csv(DATA / f"{name}.csv")
        for col in DATE_COLS.get(name, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        out[name] = df
    return out


def _event_window(events: pd.DataFrame, anchors: pd.DataFrame, date_col: str, days: int | None = None) -> pd.DataFrame:
    x = events.merge(anchors[["customer_id", "anchor_date"]], on="customer_id", how="inner")
    x = x[x[date_col].notna() & (x[date_col] <= x["anchor_date"])].copy()
    x["days_before_anchor"] = (x["anchor_date"] - x[date_col]).dt.days
    if days is not None:
        x = x[x["days_before_anchor"].between(0, days - 1)]
    return x


def _series_map(base: pd.DataFrame, series: pd.Series, name: str, fill=0):
    base[name] = base["customer_id"].map(series).fillna(fill)


def build_customer_features(data_end: str | pd.Timestamp | None = None) -> pd.DataFrame:
    d = load_processed()
    c, churn = d["customers"].copy(), d["churn_labels"].copy()

    if data_end is None:
        candidates = []
        for df, col in [
            (d["viewing_activity"], "viewing_date"), (d["payments"], "payment_date"),
            (d["support_tickets"], "ticket_date"), (d["customer_feedback"], "feedback_date")
        ]:
            candidates.append(df[col].max())
        data_end = max(x for x in candidates if pd.notna(x))
    data_end = pd.Timestamp(data_end)

    anchors = churn[["customer_id", "churned", "churn_date", "churn_reason"]].copy()
    anchors["anchor_date"] = anchors["churn_date"].where(anchors["churned"].astype(bool), data_end)
    anchors["anchor_date"] = anchors["anchor_date"].fillna(data_end)

    f = c.merge(anchors, on="customer_id", how="inner")
    f["customer_tenure_days"] = (f["anchor_date"] - f["registration_date"]).dt.days.clip(lower=0)

    # Subscription state at the anchor.
    s = d["subscriptions"].merge(anchors[["customer_id", "anchor_date"]], on="customer_id", how="inner")
    s = s[s["subscription_start_date"] <= s["anchor_date"]].copy()
    s = s.sort_values(["customer_id", "subscription_start_date", "subscription_id"])
    current = s.groupby("customer_id", as_index=False).tail(1).set_index("customer_id")
    for src, dst, default in [
        ("plan_id", "current_plan_id", "Unknown"), ("subscription_status", "current_subscription_status", "Unknown"),
        ("auto_renew", "auto_renew", False), ("monthly_price", "current_monthly_price", 0.0)
    ]:
        f[dst] = f["customer_id"].map(current[src]).fillna(default)
    plan_names = d["subscription_plans"].set_index("plan_id")["plan_name"]
    f["current_plan"] = f["current_plan_id"].map(plan_names).fillna("Unknown")
    plan_changes = s.groupby("customer_id").size().sub(1).clip(lower=0)
    _series_map(f, plan_changes, "plan_changes", 0)

    # Viewing features.
    v_all = _event_window(d["viewing_activity"], anchors, "viewing_date", None)
    v30 = v_all[v_all["days_before_anchor"] < 30]
    v60 = v_all[v_all["days_before_anchor"] < 60]
    v90 = v_all[v_all["days_before_anchor"] < 90]
    v180 = v_all[v_all["days_before_anchor"] < 180]
    _series_map(f, v90.groupby("customer_id")["watch_duration_minutes"].mean(), "avg_watch_time_per_session", 0.0)
    _series_map(f, v30.groupby("customer_id").size(), "sessions_30d", 0)
    _series_map(f, v90.groupby("customer_id").size(), "sessions_90d", 0)
    _series_map(f, v30.groupby("customer_id")["watch_duration_minutes"].sum(), "watch_minutes_30d", 0.0)
    prev30 = v60[v60["days_before_anchor"] >= 30]
    _series_map(f, prev30.groupby("customer_id")["watch_duration_minutes"].sum(), "watch_minutes_prev30d", 0.0)
    denom = f["watch_minutes_prev30d"].replace(0, np.nan)
    f["watch_minutes_change_pct_30d"] = ((f["watch_minutes_30d"] - f["watch_minutes_prev30d"]) / denom * 100).replace([np.inf,-np.inf], np.nan).fillna(0).clip(-500, 500)
    _series_map(f, v90.groupby("customer_id")["completion_percentage"].mean(), "avg_completion_90d", 0.0)
    _series_map(f, v90.groupby("customer_id")["viewing_date"].nunique(), "active_days_90d", 0)
    _series_map(f, v90.groupby("customer_id")["device_type"].nunique(), "device_diversity_90d", 0)
    v90c = v90.merge(d["content"][["content_id","genre"]], on="content_id", how="left")
    _series_map(f, v90c.groupby("customer_id")["genre"].nunique(), "genre_diversity_90d", 0)
    last_view = v_all.groupby("customer_id")["viewing_date"].max()
    f["last_view_date"] = f["customer_id"].map(last_view)
    f["days_since_last_activity"] = (f["anchor_date"] - f["last_view_date"]).dt.days.fillna(999).clip(lower=0)
    active_months = v_all.groupby("customer_id")["viewing_date"].apply(lambda s: s.dt.to_period("M").nunique())
    total_sessions = v_all.groupby("customer_id").size()
    f["login_frequency"] = f["customer_id"].map(total_sessions).fillna(0) / f["customer_id"].map(active_months).replace(0, np.nan)
    f["login_frequency"] = f["login_frequency"].fillna(0)

    # Approximate 6 x 30-day monthly watch trend, positive = increasing toward anchor.
    temp = v180.copy()
    temp["bin"] = (temp["days_before_anchor"] // 30).astype(int).clip(0, 5)
    pivot = temp.pivot_table(index="customer_id", columns="bin", values="watch_duration_minutes", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=range(6), fill_value=0)
    # old -> recent x; bin 5 is oldest, bin 0 is most recent
    y = pivot[[5,4,3,2,1,0]].to_numpy(dtype=float)
    x = np.arange(6, dtype=float)
    slope = ((y - y.mean(axis=1, keepdims=True)) * (x - x.mean())).sum(axis=1) / ((x - x.mean())**2).sum()
    slope_series = pd.Series(slope, index=pivot.index)
    _series_map(f, slope_series, "monthly_watch_time_trend", 0.0)

    # Payments.
    p_all = _event_window(d["payments"], anchors, "payment_date", None)
    p90 = p_all[p_all["days_before_anchor"] < 90]
    success_all = p_all[p_all["payment_status"].eq("Success")]
    failed90 = p90[p90["payment_status"].eq("Failed")]
    _series_map(f, p90.groupby("customer_id").size(), "payment_count_90d", 0)
    _series_map(f, failed90.groupby("customer_id").size(), "failed_payment_count", 0)
    f["failed_payment_rate"] = f["failed_payment_count"] / f["payment_count_90d"].replace(0, np.nan)
    f["failed_payment_rate"] = f["failed_payment_rate"].fillna(0.0)
    # Lifetime value uses successful charges observed by anchor; winsorize only in model inputs elsewhere, not target accounting.
    _series_map(f, success_all.groupby("customer_id")["amount"].sum(), "customer_lifetime_value", 0.0)
    _series_map(f, success_all.groupby("customer_id").size(), "successful_payment_count", 0)
    last_failed = p_all[p_all["payment_status"].eq("Failed")].groupby("customer_id")["payment_date"].max()
    f["last_failed_payment_date"] = f["customer_id"].map(last_failed)
    f["days_since_last_failed_payment"] = (f["anchor_date"] - f["last_failed_payment_date"]).dt.days.fillna(999).clip(lower=0)

    # Support.
    t_all = _event_window(d["support_tickets"], anchors, "ticket_date", None)
    t90 = t_all[t_all["days_before_anchor"] < 90]
    t180 = t_all[t_all["days_before_anchor"] < 180]
    _series_map(f, t_all.groupby("customer_id").size(), "support_ticket_count", 0)
    _series_map(f, t90.groupby("customer_id").size(), "support_ticket_count_90d", 0)
    _series_map(f, t180.groupby("customer_id")["customer_satisfaction_score"].mean(), "avg_customer_satisfaction", 3.0)
    _series_map(f, t180.groupby("customer_id")["resolution_time_hours"].mean(), "avg_resolution_time_180d", 0.0)
    low_csat = t180[t180["customer_satisfaction_score"].le(2)].groupby("customer_id").size()
    _series_map(f, low_csat, "low_csat_tickets_180d", 0)
    f["low_csat_ticket_rate_180d"] = f["low_csat_tickets_180d"] / t180.groupby("customer_id").size().reindex(f["customer_id"]).to_numpy()
    f["low_csat_ticket_rate_180d"] = f["low_csat_ticket_rate_180d"].replace([np.inf,-np.inf], np.nan).fillna(0)
    high_prio = t90[t90["priority"].isin(["High","Critical"])].groupby("customer_id").size()
    _series_map(f, high_prio, "high_priority_tickets_90d", 0)

    # Feedback.
    fb_all = _event_window(d["customer_feedback"], anchors, "feedback_date", None)
    fb180 = fb_all[fb_all["days_before_anchor"] < 180]
    _series_map(f, fb180.groupby("customer_id").size(), "feedback_count_180d", 0)
    _series_map(f, fb180.groupby("customer_id")["rating"].mean(), "avg_feedback_rating_180d", 3.0)
    neg = fb180[fb180["rating"].le(2)].groupby("customer_id").size()
    _series_map(f, neg, "negative_feedback_count_180d", 0)
    f["negative_feedback_rate_180d"] = f["negative_feedback_count_180d"] / f["feedback_count_180d"].replace(0, np.nan)
    f["negative_feedback_rate_180d"] = f["negative_feedback_rate_180d"].fillna(0)

    # Composite business scores (0-100). Rank-based scaling is robust to binge/outlier behavior.
    recency_good = 1 - f["days_since_last_activity"].rank(pct=True)
    frequency_good = f["sessions_90d"].rank(pct=True)
    completion_good = f["avg_completion_90d"].rank(pct=True)
    trend_good = f["monthly_watch_time_trend"].rank(pct=True)
    f["engagement_score"] = (100 * (0.35*recency_good + 0.30*frequency_good + 0.20*completion_good + 0.15*trend_good)).round(2)
    f["billing_risk_score"] = (100 * (0.7*f["failed_payment_rate"].rank(pct=True) + 0.3*(1 - f["days_since_last_failed_payment"].rank(pct=True)))).round(2)
    f["support_friction_score"] = (100 * (0.4*f["support_ticket_count_90d"].rank(pct=True) + 0.35*f["low_csat_ticket_rate_180d"].rank(pct=True) + 0.25*f["avg_resolution_time_180d"].rank(pct=True))).round(2)

    # Clean infinities and persist portable dates.
    f = f.replace([np.inf, -np.inf], np.nan)
    f["churned"] = f["churned"].astype(int)
    return f


if __name__ == "__main__":
    features = build_customer_features()
    out = DATA / "customer_features.csv"
    save = features.copy()
    for col in ["registration_date","churn_date","anchor_date","last_view_date","last_failed_payment_date"]:
        if col in save.columns:
            save[col] = pd.to_datetime(save[col], errors="coerce").dt.strftime("%Y-%m-%d")
    save.to_csv(out, index=False)
    print(f"Wrote {len(save):,} customer feature rows with {save.shape[1]} columns -> {out}")
