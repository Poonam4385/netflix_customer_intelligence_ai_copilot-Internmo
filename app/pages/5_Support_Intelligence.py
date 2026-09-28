from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import pandas as pd,streamlit as st,plotly.express as px
from src.llm.rag import ask as ask_rag
DATA=ROOT/"data"/"processed"
st.title("Support Intelligence")
t=pd.read_csv(DATA/"support_tickets.csv"); f=pd.read_csv(DATA/"customer_feedback.csv")
a,b=st.columns(2)
with a:
    x=t.issue_subcategory.value_counts().head(15).reset_index(); x.columns=["issue_subcategory","tickets"]
    st.plotly_chart(px.bar(x,y="issue_subcategory",x="tickets",orientation="h"),use_container_width=True)
with b:
    st.plotly_chart(px.box(t,x="issue_category",y="resolution_time_hours"),use_container_width=True)
q=st.text_input("Ask support intelligence",placeholder="What are customers saying about failed payments?")
if st.button("Search complaints") and q:
    try:
        r=ask_rag(q); st.write(r["answer"]); st.dataframe(r["records"],use_container_width=True)
    except Exception as e: st.error(str(e))
