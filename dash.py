import streamlit as st
import pandas as pd
import plotly.express as px

st.title("✅ Test App")
fig = px.bar(x=["A", "B", "C"], y=[10, 20, 30])
st.plotly_chart(fig)
