from __future__ import annotations
import json
import joblib
import numpy as np
import pandas as pd
import shap
from src.models.common import DATA, MODELS
from src.llm.client import LLMClient


def _clean_feature_name(name:str)->str:
    name=name.replace("num__","").replace("cat__","")
    return name.replace("_"," ")

def explain_customer(customer_id:str, top_n:int=8, use_llm:bool=True)->dict:
    df=pd.read_csv(DATA/"customer_features.csv")
    row=df[df.customer_id==customer_id]
    if row.empty: raise KeyError(f"Unknown customer_id {customer_id}")
    pipe=joblib.load(MODELS/"churn_pipeline.joblib")
    meta=json.loads((MODELS/"churn_metadata.json").read_text())
    features=meta["feature_columns"]
    X=row[features]
    proba=float(pipe.predict_proba(X)[0,1]); threshold=float(meta["retention_threshold"])
    pre=pipe.named_steps["preprocess"]; model=pipe.named_steps["model"]
    z=pre.transform(X)
    names=pre.get_feature_names_out().tolist()
    arr=z.toarray() if hasattr(z,"toarray") else np.asarray(z)

    model_name=model.__class__.__name__.lower()
    if "xgb" in model_name or "forest" in model_name:
        explainer=shap.TreeExplainer(model)
        sv=explainer.shap_values(arr)
        if isinstance(sv,list): sv=sv[-1]
        values=np.asarray(sv)[0]
    elif hasattr(model,"coef_"):
        values=arr[0]*model.coef_[0]
    else:
        # Fallback: local permutation SHAP on the transformed model only.
        explainer=shap.Explainer(model.predict_proba,arr)
        values=np.asarray(explainer(arr).values)[0,:,1]

    order=np.argsort(np.abs(values))[::-1][:top_n]
    factors=[]
    for i in order:
        factors.append({
            "feature":_clean_feature_name(names[i]),
            "contribution":float(values[i]),
            "direction":"increases risk" if values[i]>0 else "reduces risk",
            "transformed_value":float(arr[0,i]) if np.issubdtype(type(arr[0,i]),np.number) else str(arr[0,i]),
        })
    business={k:(None if pd.isna(row.iloc[0].get(k)) else row.iloc[0].get(k)) for k in [
        "current_plan","customer_tenure_days","days_since_last_activity","watch_minutes_30d","watch_minutes_change_pct_30d",
        "failed_payment_count","failed_payment_rate","support_ticket_count_90d","avg_customer_satisfaction",
        "negative_feedback_rate_180d","engagement_score","customer_lifetime_value"
    ]}
    result={"customer_id":customer_id,"churn_probability":proba,"retention_threshold":threshold,
            "predicted_high_risk":proba>=threshold,"top_factors":factors,"business_features":business}
    if use_llm:
        try:
            result["business_explanation"]=LLMClient().generate(
                "Explain this churn prediction to a retention manager using only the supplied JSON facts. Do not invent causes. Clearly separate model signal from certainty.\n"+json.dumps(result,default=str),
                "You explain machine-learning predictions faithfully and cautiously. Use 4-6 concise bullets and one recommended next check.",900)
        except Exception as e:
            result["business_explanation"]=f"LLM explanation unavailable: {e}"
    return result
