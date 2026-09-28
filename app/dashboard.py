from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
import streamlit as st
import plotly.express as px

DATA=ROOT/"data"/"processed"
st.set_page_config(page_title="Netflix Customer Intelligence",page_icon="🎬",layout="wide")
st.title("🎬 Netflix Customer Intelligence & AI Analytics Copilot")
st.caption("Portfolio project modeled on a subscription streaming business; synthetic data, not Netflix production data.")

features=pd.read_csv(DATA/"customer_features.csv")
scores=pd.read_csv(DATA/"customer_churn_scores.csv") if (DATA/"customer_churn_scores.csv").exists() else None
payments=pd.read_csv(DATA/"payments.csv")
tickets=pd.read_csv(DATA/"support_tickets.csv")

c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Customers",f"{len(features):,}")
c2.metric("Observed churn",f"{100*features.churned.mean():.1f}%")
c3.metric("Successful revenue",f"${payments.loc[payments.payment_status.eq('Success'),'amount'].sum():,.0f}")
if scores is not None:
    c4.metric("High/Critical risk",f"{scores.risk_band.isin(['High','Critical']).sum():,}")
else: c4.metric("High-risk customers","Train churn model")
c5.metric("Avg CSAT",f"{tickets.customer_satisfaction_score.mean():.2f}/5")

left,right=st.columns(2)
with left:
    st.subheader("Churn by plan")
    x=features.groupby("current_plan",as_index=False).churned.mean(); x["churn_pct"]=100*x.churned
    st.plotly_chart(px.bar(x,x="current_plan",y="churn_pct",labels={"churn_pct":"Churn %"}),use_container_width=True)
with right:
    st.subheader("Engagement vs lifetime value")
    plot=features.sample(min(3000,len(features)),random_state=42)
    st.plotly_chart(px.scatter(plot,x="engagement_score",y="customer_lifetime_value",color="churned",hover_name="customer_id"),use_container_width=True)

st.info("Use the pages in the sidebar for customer analytics, churn explanations, segmentation, Text-to-SQL/RAG copilot, support intelligence, and automated reports.")
