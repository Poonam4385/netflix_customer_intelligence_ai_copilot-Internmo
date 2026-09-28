from __future__ import annotations
import json
import pandas as pd
from src.models.common import DATA
from src.llm.client import LLMClient


def build_retention_table()->pd.DataFrame:
    features=pd.read_csv(DATA/"customer_features.csv")
    scores=pd.read_csv(DATA/"customer_churn_scores.csv")
    seg=pd.read_csv(DATA/"customer_segments.csv")[["customer_id","cluster_name"]]
    x=features.merge(scores[["customer_id","churn_probability","risk_band"]],on="customer_id").merge(seg,on="customer_id",how="left")
    x["clv_percentile"]=x["customer_lifetime_value"].rank(pct=True)
    x["risk_percentile"]=x["churn_probability"].rank(pct=True)

    def action(r):
        if r.risk_percentile>=.80 and r.clv_percentile>=.75:
            return "Priority human outreach + personalized save offer"
        if r.risk_percentile>=.80 and r.failed_payment_rate>.20:
            return "Payment-recovery journey + temporary grace period"
        if r.risk_percentile>=.80 and r.avg_customer_satisfaction<=2.5:
            return "Senior support callback + service recovery"
        if r.risk_percentile>=.70 and r.engagement_score<40:
            return "Personalized content re-engagement campaign"
        if r.risk_percentile>=.70:
            return "Targeted retention incentive"
        if r.clv_percentile>=.80:
            return "Loyalty/value reinforcement; avoid unnecessary discount"
        return "No urgent intervention; continue lifecycle messaging"
    x["recommended_action"]=x.apply(action,axis=1)
    x["priority_score"]=(100*(.60*x["risk_percentile"]+.40*x["clv_percentile"])).round(1)
    return x.sort_values("priority_score",ascending=False)

def recommend(customer_id:str,use_llm:bool=True)->dict:
    x=build_retention_table(); r=x[x.customer_id==customer_id]
    if r.empty: raise KeyError(customer_id)
    s=r.iloc[0]
    facts={k:s[k] for k in ["customer_id","churn_probability","risk_band","customer_lifetime_value","clv_percentile","cluster_name",
                             "engagement_score","failed_payment_rate","support_ticket_count_90d","avg_customer_satisfaction","recommended_action","priority_score"]}
    out={k:(v.item() if hasattr(v,"item") else v) for k,v in facts.items()}
    if use_llm:
        try:
            out["message"]=LLMClient().generate(
                "Draft a retention recommendation using only these facts. Include action, rationale, channel suggestion, and one guardrail against over-discounting.\n"+json.dumps(out,default=str),
                "You are a retention-strategy copilot. You may phrase recommendations but must not fabricate customer facts.",700)
        except Exception as e: out["message"]=f"LLM unavailable: {e}"
    return out

if __name__=="__main__":
    build_retention_table().to_csv(DATA/"retention_priorities.csv",index=False)
