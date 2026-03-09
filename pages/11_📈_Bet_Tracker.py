# ============================================================
# FILE: pages/11_📈_Bet_Tracker.py
# PURPOSE: Redirects to Performance Center (page 6_📊).
#          Kept for backwards-compat — functionality has been
#          consolidated into 6_📊_Performance_Center.py.
# ============================================================

import streamlit as st
from styles.theme import get_global_css

st.set_page_config(
    page_title="Bet Tracker — SmartBetPro NBA",
    page_icon="📈",
    layout="wide",
)
st.markdown(get_global_css(), unsafe_allow_html=True)

st.title("📈 Bet Tracker")
st.info(
    "📈 **Bet Tracker** has been merged into the **Performance Center**. "
    "All bet logging, AI picks, auto-resolve, and performance forecasting are now in one place. "
    "\n\n👉 Use **📊 Performance Center** in the left sidebar."
)
