from __future__ import annotations
import argparse
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score, fbeta_score,
                             roc_auc_score, average_precision_score, confusion_matrix, classification_report)
from sklearn.model_selection import StratifiedKFold, cross_val_score, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src.models.common import load_features, model_columns, make_preprocessor, MODELS, DATA, REPORTS, write_json

RANDOM_STATE = 42


def metrics(y, proba, threshold):
    pred = (proba >= threshold).astype(int)
    return {
        "threshold": float(threshold), "accuracy": accuracy_score(y, pred),
        "precision": precision_score(y, pred, zero_division=0), "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0), "f2": fbeta_score(y, pred, beta=2, zero_division=0),
        "roc_auc": roc_auc_score(y, proba), "average_precision": average_precision_score(y, proba),
        "confusion_matrix": confusion_matrix(y, pred).tolist(),
    }


def main(fast: bool = False):
    df = load_features()
    y = df["churned"].astype(int)
    # Exclude obvious outcome leakage and CLV accounting helper fields. CLV itself is allowed as pre-anchor value.
    extra_drop = {"successful_payment_count"}
    numeric, categorical = model_columns(df, "churned", extra_drop)
    features = numeric + categorical
    X = df[features].copy()
    X_train, X_test, y_train, y_test, id_train, id_test = train_test_split(
        X, y, df["customer_id"], test_size=.20, stratify=y, random_state=RANDOM_STATE
    )
    pos_weight = (y_train.eq(0).sum() / y_train.eq(1).sum())

    models = {
        "logistic": LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5, random_state=RANDOM_STATE),
        "random_forest": RandomForestClassifier(n_estimators=300 if not fast else 120, min_samples_leaf=4,
                                                 max_features="sqrt", class_weight="balanced_subsample",
                                                 n_jobs=-1, random_state=RANDOM_STATE),
        "xgboost": XGBClassifier(n_estimators=420 if not fast else 160, max_depth=4, learning_rate=.035 if not fast else .06,
                                 subsample=.85, colsample_bytree=.85, min_child_weight=3,
                                 reg_lambda=2.0, objective="binary:logistic", eval_metric="logloss",
                                 scale_pos_weight=pos_weight, n_jobs=-1, random_state=RANDOM_STATE),
    }
    cv = StratifiedKFold(n_splits=5 if not fast else 3, shuffle=True, random_state=RANDOM_STATE)
    results = {}
    pipelines = {}
    for name, estimator in models.items():
        pre = make_preprocessor(numeric, categorical, scale_numeric=(name == "logistic"))
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        scores = cross_val_score(pipe, X_train, y_train, scoring="roc_auc", cv=cv, n_jobs=1)
        results[name] = {"cv_roc_auc_mean": scores.mean(), "cv_roc_auc_std": scores.std()}
        pipelines[name] = pipe
        print(name, results[name])

    best_name = max(results, key=lambda k: results[k]["cv_roc_auc_mean"])
    best = pipelines[best_name]

    # Select retention threshold from out-of-fold training predictions using F2 (recall weighted higher than precision).
    oof = cross_val_predict(clone(best), X_train, y_train, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    thresholds = np.linspace(.10, .90, 161)
    f2s = [fbeta_score(y_train, oof >= t, beta=2, zero_division=0) for t in thresholds]
    threshold = float(thresholds[int(np.argmax(f2s))])

    best.fit(X_train, y_train)
    test_proba = best.predict_proba(X_test)[:, 1]
    results[best_name]["test_default_0_5"] = metrics(y_test, test_proba, .5)
    results[best_name]["test_retention_threshold"] = metrics(y_test, test_proba, threshold)
    results[best_name]["classification_report"] = classification_report(y_test, test_proba >= threshold, output_dict=True, zero_division=0)
    results["selected_model"] = best_name
    results["retention_threshold"] = threshold
    results["feature_columns"] = features
    results["numeric_features"] = numeric
    results["categorical_features"] = categorical

    joblib.dump(best, MODELS / "churn_pipeline.joblib")
    write_json(MODELS / "churn_metadata.json", results)

    # Score all customers for app/retention workflows.
    all_proba = best.predict_proba(X)[:, 1]
    scored = df[["customer_id", "customer_lifetime_value", "current_plan", "engagement_score", "billing_risk_score", "support_friction_score"]].copy()
    scored["churn_probability"] = all_proba
    scored["risk_band"] = pd.cut(scored["churn_probability"], bins=[-np.inf,.30,.55,.75,np.inf], labels=["Low","Medium","High","Critical"])
    scored.to_csv(DATA / "customer_churn_scores.csv", index=False)
    print("Selected:", best_name, "threshold:", threshold)
    print(results[best_name]["test_retention_threshold"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    main(args.fast)
