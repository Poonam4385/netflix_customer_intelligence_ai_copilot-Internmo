from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import streamlit as st
from src.llm.text_to_sql import ask as ask_sql
from src.llm.rag import ask as ask_rag
st.title("AI Analytics Copilot")
mode=st.radio("Capability",["Text-to-SQL","Support/Feedback RAG"],horizontal=True)
q=st.text_area("Ask a business question",placeholder="Which acquisition channels have the highest churn rate?")
if st.button("Run",type="primary") and q.strip():
    try:
        with st.spinner("Analyzing..."):
            if mode=="Text-to-SQL":
                r=ask_sql(q); st.subheader("Generated SQL"); st.code(r["sql"],language="sql"); st.dataframe(r["data"],use_container_width=True); st.subheader("Answer"); st.write(r["answer"])
            else:
                r=ask_rag(q); st.write(r["answer"]); st.subheader("Retrieved evidence"); st.dataframe(r["records"],use_container_width=True)
    except Exception as e: st.error(str(e))
