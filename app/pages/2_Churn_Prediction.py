from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import pandas as pd,streamlit as st
from src.services.prediction_explainer import explain_customer
from src.services.retention import recommend
DATA=ROOT/"data"/"processed"
st.title("Churn Prediction & Explainability")
features=pd.read_csv(DATA/"customer_features.csv")
cid=st.selectbox("Customer",features.customer_id.tolist())
if st.button("Explain churn risk",type="primary"):
    with st.spinner("Scoring and explaining..."):
        result=explain_customer(cid,use_llm=True)
    st.metric("Churn probability",f"{100*result['churn_probability']:.1f}%")
    st.write("Model retention threshold:",f"{100*result['retention_threshold']:.1f}%")
    st.subheader("Top model factors")
    st.dataframe(pd.DataFrame(result["top_factors"]),use_container_width=True)
    st.subheader("Business explanation")
    st.write(result.get("business_explanation"))
    st.subheader("Retention action")
    st.json(recommend(cid,use_llm=True))
