from __future__ import annotations
import json
import pandas as pd
from src.database.db import query_df
from src.llm.client import LLMClient


def investigate(country:str,month:str,use_llm:bool=True)->dict:
    # month format YYYY-MM-01
    params={"country":country,"month":month}
    facts={"country":country,"month":month}
    facts["churn"] = query_df("""
      WITH m AS (SELECT CAST(:month AS date) m), x AS (
       SELECT CASE WHEN cl.churn_date>=m.m AND cl.churn_date<m.m+INTERVAL '1 month' THEN 'current'
                   WHEN cl.churn_date>=m.m-INTERVAL '1 month' AND cl.churn_date<m.m THEN 'previous' END p,
              COUNT(*) n
       FROM churn_labels cl JOIN customers c USING(customer_id) CROSS JOIN m
       WHERE c.country=:country AND cl.churned AND cl.churn_date>=m.m-INTERVAL '1 month' AND cl.churn_date<m.m+INTERVAL '1 month'
       GROUP BY 1) SELECT * FROM x WHERE p IS NOT NULL""",params).to_dict("records")
    facts["engagement"] = query_df("""
      WITH m AS (SELECT CAST(:month AS date) m) SELECT
       CASE WHEN viewing_date>=m.m THEN 'current' ELSE 'previous' END p,
       ROUND(AVG(watch_duration_minutes),2) avg_watch_minutes, COUNT(DISTINCT v.customer_id) viewers
      FROM viewing_activity v JOIN customers c USING(customer_id) CROSS JOIN m
      WHERE c.country=:country AND viewing_date>=m.m-INTERVAL '1 month' AND viewing_date<m.m+INTERVAL '1 month'
      GROUP BY 1""",params).to_dict("records")
    facts["payments"] = query_df("""
      WITH m AS (SELECT CAST(:month AS date) m) SELECT CASE WHEN payment_date>=m.m THEN 'current' ELSE 'previous' END p,
       ROUND(AVG((payment_status='Failed')::int::numeric),4) failed_payment_rate,COUNT(*) payments
      FROM payments p JOIN customers c USING(customer_id) CROSS JOIN m
      WHERE c.country=:country AND payment_date>=m.m-INTERVAL '1 month' AND payment_date<m.m+INTERVAL '1 month'
      GROUP BY 1""",params).to_dict("records")
    facts["support"] = query_df("""
      WITH m AS (SELECT CAST(:month AS date) m) SELECT CASE WHEN ticket_date>=m.m THEN 'current' ELSE 'previous' END p,
       COUNT(*) tickets,ROUND(AVG(customer_satisfaction_score),2) avg_csat
      FROM support_tickets t JOIN customers c USING(customer_id) CROSS JOIN m
      WHERE c.country=:country AND ticket_date>=m.m-INTERVAL '1 month' AND ticket_date<m.m+INTERVAL '1 month'
      GROUP BY 1""",params).to_dict("records")
    facts["plan_mix"] = query_df("""
      WITH m AS (SELECT CAST(:month AS date) m), latest AS (
       SELECT s.customer_id,s.plan_id,ROW_NUMBER() OVER(PARTITION BY s.customer_id ORDER BY s.subscription_start_date DESC) rn
       FROM subscriptions s JOIN customers c USING(customer_id),m WHERE c.country=:country AND s.subscription_start_date < m.m+INTERVAL '1 month')
      SELECT sp.plan_name,COUNT(*) customers FROM latest l JOIN subscription_plans sp USING(plan_id) WHERE rn=1 GROUP BY sp.plan_name ORDER BY customers DESC""",params).to_dict("records")
    if use_llm:
        try:
            facts["analysis"]=LLMClient().generate(
                "Analyze possible churn drivers from this root-cause fact pack. Rank evidence by strength, note missing evidence, and do not state any number not present.\n"+json.dumps(facts,default=str),
                "You are a root-cause analytics agent. Distinguish correlation from causation and do not invent facts.",1200)
        except Exception as e: facts["analysis"]=f"LLM unavailable: {e}"
    return facts
