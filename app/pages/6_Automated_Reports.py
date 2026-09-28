from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import streamlit as st
from src.services.reports import generate_report
from src.services.root_cause import investigate
st.title("Automated Reports & Root-Cause Analysis")
tab1,tab2=st.tabs(["Business report","Root cause"])
with tab1:
    period=st.selectbox("Period",["weekly","monthly","quarterly"])
    if st.button("Generate report",type="primary"):
        try:
            report=generate_report(period,use_llm=True); st.markdown(report); st.download_button("Download Markdown",report,file_name=f"{period}_report.md")
        except Exception as e: st.error(str(e))
with tab2:
    country=st.text_input("Country",value="United States")
    month=st.text_input("Month start (YYYY-MM-01)",value="2026-06-01")
    if st.button("Investigate"):
        try: st.json(investigate(country,month,use_llm=True))
        except Exception as e: st.error(str(e))
