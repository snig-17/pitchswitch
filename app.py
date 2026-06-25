"""PitchSwitch - AI Multi-Match Whip-Around Companion.

Run: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="PitchSwitch",
    page_icon="",
    layout="wide",
)

st.title("PitchSwitch")
st.subheader("AI Multi-Match Whip-Around Companion")
st.write("Phase 0 scaffold. Building Phase 1 next.")

# Sidebar - team selection placeholder
with st.sidebar:
    st.header("Settings")
    favourite_team = st.text_input("Favourite team", placeholder="e.g. Cape Verde")
    replay_speed = st.slider("Replay speed", min_value=1, max_value=200, value=60)
    st.button("Start Demo", disabled=True)

# Main layout placeholder
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Match 1", "0-0", delta=None)
    st.progress(0.0, text="Danger: 0.00")
with col2:
    st.metric("Match 2", "0-0", delta=None)
    st.progress(0.0, text="Danger: 0.00")
with col3:
    st.metric("Match 3", "0-0", delta=None)
    st.progress(0.0, text="Danger: 0.00")

# Narration banner placeholder
st.info("Waiting for match data...")

# Accuracy panel placeholder
st.caption("Accuracy: --/-- predictions | Avg lead time: --s")
