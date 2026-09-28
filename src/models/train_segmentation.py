from __future__ import annotations
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
from src.models.common import load_features, MODELS, DATA, write_json

FEATURES = [
    "customer_tenure_days", "engagement_score", "watch_minutes_30d", "watch_minutes_change_pct_30d",
    "failed_payment_rate", "support_ticket_count_90d", "avg_customer_satisfaction",
    "negative_feedback_rate_180d", "customer_lifetime_value", "current_monthly_price",
]

def label_cluster(row, med):
    if row.customer_lifetime_value >= med.customer_lifetime_value and row.engagement_score >= med.engagement_score and row.failed_payment_rate <= med.failed_payment_rate:
        return "High-Value Loyal"
    if row.engagement_score < med.engagement_score and (row.failed_payment_rate > med.failed_payment_rate or row.avg_customer_satisfaction < med.avg_customer_satisfaction):
        return "At-Risk Low-Engagement"
    if row.customer_tenure_days < med.customer_tenure_days and row.customer_lifetime_value < med.customer_lifetime_value:
        return "New / Developing"
    if row.failed_payment_rate > med.failed_payment_rate:
        return "Billing-Fragile"
    if row.support_ticket_count_90d > med.support_ticket_count_90d:
        return "Support-Intensive"
    return "Core Mainstream"

def main():
    df = load_features()
    X = df[FEATURES].copy()
    prep = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    Z = prep.fit_transform(X)
    scores = {}
    models = {}
    for k in range(2, 8):
        km = KMeans(n_clusters=k, n_init=30, random_state=42)
        labels = km.fit_predict(Z)
        sil = silhouette_score(Z, labels, sample_size=min(5000, len(df)), random_state=42)
        scores[k] = sil
        models[k] = km
        print("k", k, "silhouette", round(sil, 4))
    best_k = max(scores, key=scores.get)
    km = models[best_k]
    labels = km.predict(Z)
    out = df[["customer_id"] + FEATURES].copy()
    out["cluster_id"] = labels
    profile = out.groupby("cluster_id")[FEATURES].mean()
    profile["customer_count"] = out.groupby("cluster_id").size()
    med = df[FEATURES].median()
    profile["cluster_name"] = profile.apply(lambda r: label_cluster(r, med), axis=1)
    profile["cluster_name"] = [f"{name} (C{idx})" for idx, name in zip(profile.index, profile["cluster_name"])]
    name_map = profile["cluster_name"].to_dict()
    out["cluster_name"] = out["cluster_id"].map(name_map)

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(Z)
    out["pca_1"], out["pca_2"] = coords[:,0], coords[:,1]
    out.to_csv(DATA / "customer_segments.csv", index=False)
    profile.to_csv(DATA / "segment_profiles.csv")
    joblib.dump({"preprocess": prep, "kmeans": km, "features": FEATURES, "name_map": name_map, "pca": pca}, MODELS / "segmentation.joblib")
    write_json(MODELS / "segmentation_metadata.json", {"best_k": best_k, "silhouette_scores": scores, "features": FEATURES})
    print("Selected K:", best_k)
    print(profile[["customer_count","cluster_name","engagement_score","customer_lifetime_value","failed_payment_rate"]])

if __name__ == "__main__": main()
