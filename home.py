"""Factory Analytics: home page. Run with: streamlit run home.py"""

import streamlit as st

import ui

st.set_page_config(page_title="Factory Analytics", page_icon="🏭", layout="wide")
ui.inject_css()

ui.page_header(
    "🏭",
    "Factory Analytics",
    "Turn production and maintenance data into decisions: where time is lost, what keeps "
    "breaking, and what to fix first.",
    tag="Manufacturing operations",
)

left, mid, right = st.columns(3, gap="large")
with left:
    st.markdown(
        ui.card(
            "🔧 Maintenance Log Analyzer",
            "Shows what fails most, which machines lose the most time, and which failures keep "
            "coming back so you can find the root cause.",
            [
                "Downtime and repair cost by machine and failure type",
                "MTBF (average days between failures) per machine",
                "Repeat-failure list for root-cause analysis",
                "Optional AI report with the provider you already use",
            ],
        ),
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Maintenance_Log.py", label="Open maintenance analyzer", icon="🔧")

with mid:
    st.markdown(
        ui.card(
            "⚙️ Machining Cost Calculator",
            "Estimate cycle time and cost per part for turning, milling or drilling before you quote.",
            [
                "Spindle speed, feed rate and cycle time",
                "Cost per part: material, machine, tools and setup",
                "Cycle time against cutting speed",
            ],
        ),
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_Machining_Cost.py", label="Open machining calculator", icon="⚙️")

with right:
    st.markdown(
        ui.card(
            "📈 OEE Dashboard",
            "Measures how much planned time becomes good parts, and splits the losses into "
            "availability, performance and quality.",
            [
                "OEE with availability, performance and quality",
                "Where planned time went, and a downtime Pareto",
                "Machine and shift comparison with hot-spot detection",
                "Plain-language findings and a downloadable summary",
            ],
        ),
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_OEE_Dashboard.py", label="Open OEE dashboard", icon="📈")

st.markdown("## How it works")
s1, s2, s3 = st.columns(3, gap="large")
with s1:
    st.markdown(ui.step(1, "Upload your CSV. Columns are matched automatically, and you can correct any match."), unsafe_allow_html=True)
with s2:
    st.markdown(ui.step(2, "Read the findings. Rows with bad data are listed with the reason, never dropped silently."), unsafe_allow_html=True)
with s3:
    st.markdown(ui.step(3, "Download the summary, or an AI-written report as Markdown or HTML."), unsafe_allow_html=True)

st.caption("Each tool has a format guide and a blank template in its sidebar.")
ui.footer()
