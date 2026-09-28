from __future__ import annotations
import json
import pandas as pd
from src.database.db import query_df
from src.llm.client import LLMClient

PERIOD_DAYS={"weekly":7,"monthly":30,"quarterly":90}

def collect_report_facts(period:str="monthly")->dict:
    days=PERIOD_DAYS[period]
    anchor=query_df("SELECT GREATEST((SELECT MAX(payment_date) FROM payments),(SELECT MAX(viewing_date) FROM viewing_activity),(SELECT MAX(churn_date) FROM churn_labels))::date AS d").iloc[0,0]
    facts={"period":period,"period_days":days,"anchor_date":str(anchor)}
    facts["revenue"]=float(query_df("SELECT COALESCE(SUM(amount),0) v FROM payments WHERE payment_status='Success' AND payment_date > CAST(:d AS date) - (:days || ' days')::interval",{"d":anchor,"days":days}).iloc[0,0])
    facts["churned_customers"]=int(query_df("SELECT COUNT(*) v FROM churn_labels WHERE churned AND churn_date > CAST(:d AS date) - (:days || ' days')::interval",{"d":anchor,"days":days}).iloc[0,0])
    facts["new_customers"]=int(query_df("SELECT COUNT(*) v FROM customers WHERE registration_date > CAST(:d AS date) - (:days || ' days')::interval",{"d":anchor,"days":days}).iloc[0,0])
    facts["active_viewers"]=int(query_df("SELECT COUNT(DISTINCT customer_id) v FROM viewing_activity WHERE viewing_date > CAST(:d AS date) - (:days || ' days')::interval",{"d":anchor,"days":days}).iloc[0,0])
    cs=query_df("SELECT AVG(customer_satisfaction_score) v FROM support_tickets WHERE ticket_date > CAST(:d AS date) - (:days || ' days')::interval",{"d":anchor,"days":days}).iloc[0,0]
    facts["avg_csat"]=None if pd.isna(cs) else round(float(cs),2)
    top=query_df("SELECT issue_subcategory,COUNT(*) n FROM support_tickets WHERE ticket_date > CAST(:d AS date) - (:days || ' days')::interval GROUP BY issue_subcategory ORDER BY n DESC LIMIT 5",{"d":anchor,"days":days})
    facts["top_complaints"]=top.to_dict("records")
    return facts

def render_fallback(facts:dict)->str:
    complaints=", ".join(f"{x['issue_subcategory']} ({x['n']})" for x in facts["top_complaints"])
    return f"""# {facts['period'].title()} Customer Intelligence Report\n\n## Calculated facts\n- Period ending: {facts['anchor_date']}\n- Successful-payment revenue: ${facts['revenue']:,.2f}\n- Churned customers: {facts['churned_customers']}\n- New customers: {facts['new_customers']}\n- Active viewers: {facts['active_viewers']}\n- Average CSAT: {facts['avg_csat']}\n- Top complaints: {complaints}\n\n## Interpretation\nAI narrative was not generated. Connect an LLM to add interpretation while keeping the facts above unchanged.\n"""

def generate_report(period:str="monthly",use_llm:bool=True)->str:
    facts=collect_report_facts(period)
    if not use_llm: return render_fallback(facts)
    try:
        return LLMClient().generate(
            "Write an executive customer-intelligence report from the JSON below. Use sections: Executive Summary, Calculated Facts, Key Findings, Risks, Recommended Actions. Never change or invent a number. Clearly label interpretation as interpretation.\n"+json.dumps(facts),
            "You are an executive analytics report writer. Every numeric claim must come directly from the provided JSON.",1600)
    except Exception:
        return render_fallback(facts)
