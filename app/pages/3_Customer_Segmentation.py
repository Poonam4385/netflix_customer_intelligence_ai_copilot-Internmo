from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
import pandas as pd,streamlit as st,plotly.express as px
DATA=ROOT/"data"/"processed"
st.title("Customer Segmentation")
seg=pd.read_csv(DATA/"customer_segments.csv"); prof=pd.read_csv(DATA/"segment_profiles.csv")
st.plotly_chart(px.scatter(seg,x="pca_1",y="pca_2",color="cluster_name",hover_name="customer_id",opacity=.6),use_container_width=True)
st.subheader("Cluster profiles")
st.dataframe(prof,use_container_width=True)
name=st.selectbox("Explore cluster",sorted(seg.cluster_name.unique()))
x=seg[seg.cluster_name.eq(name)]
st.write(f"Customers: {len(x):,}")
st.dataframe(x.sort_values("customer_lifetime_value",ascending=False).head(100),use_container_width=True)
