from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import pandas as pd, streamlit as st, plotly.express as px
DATA=ROOT/"data"/"processed"
st.title("Customer Analytics")
df=pd.read_csv(DATA/"customer_features.csv")
col1,col2,col3=st.columns(3)
country=col1.multiselect("Country",sorted(df.country.dropna().unique()))
plan=col2.multiselect("Plan",sorted(df.current_plan.dropna().unique()))
segment=col3.multiselect("Customer segment",sorted(df.customer_segment.dropna().unique()))
x=df.copy()
if country:x=x[x.country.isin(country)]
if plan:x=x[x.current_plan.isin(plan)]
if segment:x=x[x.customer_segment.isin(segment)]
st.write(f"{len(x):,} customers")
a,b=st.columns(2)
with a: st.plotly_chart(px.histogram(x,x="age",color="churned",barmode="overlay"),use_container_width=True)
with b: st.plotly_chart(px.box(x,x="current_plan",y="engagement_score",color="churned"),use_container_width=True)
st.plotly_chart(px.scatter(x.sample(min(2500,len(x)),random_state=42),x="watch_minutes_30d",y="customer_lifetime_value",color="churned",size="support_ticket_count_90d",hover_name="customer_id"),use_container_width=True)
st.dataframe(x[["customer_id","country","current_plan","customer_segment","engagement_score","failed_payment_rate","avg_customer_satisfaction","customer_lifetime_value","churned"]],use_container_width=True)
