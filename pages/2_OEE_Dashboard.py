"""OEE Dashboard page. Run the project with: streamlit run home.py"""

import pandas as pd
from pathlib import Path

import streamlit as st

import oee
import ui

st.set_page_config(page_title="OEE Dashboard", page_icon="📈", layout="wide")

TEMPLATE_CSV = (
    "date,shift,machine_id,planned_time_min,downtime_min,downtime_reason,"
    "ideal_cycle_time_sec,total_count,good_count\n"
    "14-03-2026,A,CNC-01,450,40,Tool change,30,700,680\n"
    "14-03-2026,B,CNC-01,450,25,Breakdown,30,740,725\n"
)


def pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


ui.inject_css()
ui.page_header(
    "📈",
    "OEE Dashboard",
    "See how much planned time becomes good parts, where the losses are, and what to fix first.",
    tag="Production efficiency",
)

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Upload production log (CSV)", type="csv")
    use_sample = st.checkbox("Use sample data", value=uploaded is None)

    with st.expander("What format should my CSV be?"):
        st.markdown(
            "One row per machine per shift (or per production run). The first row must contain "
            "these column names:\n\n"
            "| Column | Example | Meaning |\n"
            "|---|---|---|\n"
            "| `date` | 14-03-2026 | Day of production |\n"
            "| `machine_id` | CNC-01 | Machine name or code |\n"
            "| `planned_time_min` | 450 | Minutes planned to run |\n"
            "| `downtime_min` | 40 | Minutes stopped in that time |\n"
            "| `ideal_cycle_time_sec` | 30 | Fastest realistic seconds per part |\n"
            "| `total_count` | 700 | All parts made |\n"
            "| `good_count` | 680 | Parts that passed inspection |\n"
            "| `shift` *(optional)* | A | Shift name |\n"
            "| `downtime_reason` *(optional)* | Breakdown | Main cause of the downtime |\n\n"
            "Tip: export from Excel using **Save As > CSV**. If a date shows `########`, widen "
            "the column first."
        )
        st.download_button(
            "Download blank template",
            TEMPLATE_CSV,
            file_name="production_log_template.csv",
            mime="text/csv",
        )

SAMPLE = Path(__file__).resolve().parent.parent / "sample_oee.csv"
source = uploaded if uploaded is not None else (str(SAMPLE) if use_sample else None)
if source is None:
    st.info("Upload a CSV or tick 'Use sample data' to begin.")
    st.stop()

req, opt = oee.columns_for(source)
mapping = ui.column_mapping(source, req, opt, key="oee")
try:
    data = oee.load_log(source, mapping)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not read the file: {e}")
    st.stop()

skipped = data.attrs.get("skipped_rows", [])
if skipped:
    st.warning(
        f"{len(skipped)} row(s) were skipped because of bad data. "
        "Fix them in your file and upload it again to include them."
    )
    st.dataframe(skipped, width="stretch", hide_index=True)
    st.caption("Row numbers match the row numbers you see in Excel.")

for w in data.attrs.get("warnings", []):
    st.warning(w)

if data.empty:
    st.error("No valid rows found in the file.")
    st.stop()

# ----- filters
with st.sidebar:
    st.header("Filters")
    machines = sorted(data["machine_id"].unique())
    chosen_machines = st.multiselect("Machines", machines, default=machines)
    shifts = sorted(data["shift"].unique())
    chosen_shifts = st.multiselect("Shifts", shifts, default=shifts)
    d_min, d_max = data["date"].min().date(), data["date"].max().date()
    dates = st.date_input("Date range", value=(d_min, d_max), min_value=d_min, max_value=d_max)
    target = st.slider("Target OEE", 50, 100, 85, help="Your plant's own goal. World-class is 85%.")
    grain = st.radio("Trend grouping", ["Day", "Week", "Month"], index=1, horizontal=True)

df = data[data["machine_id"].isin(chosen_machines) & data["shift"].isin(chosen_shifts)]
if isinstance(dates, tuple) and len(dates) == 2:
    df = df[(df["date"].dt.date >= dates[0]) & (df["date"].dt.date <= dates[1])]
if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ----- headline numbers
k = oee.kpis(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("OEE", pct(k["oee"]), f"{(k['oee'] - target / 100) * 100:+.1f} pts vs target")
c2.metric("Availability", pct(k["availability"]), help="Share of planned time the machine actually ran")
c3.metric("Performance", pct(k["performance"]), help="Speed while running, compared with the ideal cycle time")
c4.metric("Quality", pct(k["quality"]), help="Share of production that was good first time")

st.caption(
    f"Planned {k['planned_min'] / 60:,.0f} h · Downtime {k['downtime_min'] / 60:,.0f} h · "
    f"Parts made {k['total_count']:,.0f} · Good parts {k['good_count']:,.0f}"
)

st.subheader("What to fix first")
for rec in oee.recommendations(df, target=target / 100):
    st.markdown(f"- {rec}")

# ----- trend
st.subheader("OEE over time")
freq = {"Day": "D", "Week": "W", "Month": "M"}[grain]
t = oee.trend(df, freq).set_index("period")
st.line_chart(t[["oee", "availability", "performance", "quality"]])
st.caption(f"Grouped by {grain.lower()}. Each point is calculated from total minutes and counts, not averaged percentages.")

# ----- factor view vs benchmark
st.subheader("Factors against world-class levels")
bench_rows = pd.DataFrame(
    [
        {"factor": "OEE", "yours": k["oee"], "world-class": oee.BENCHMARKS["oee"]},
        {"factor": "Availability", "yours": k["availability"], "world-class": oee.BENCHMARKS["availability"]},
        {"factor": "Performance", "yours": k["performance"], "world-class": oee.BENCHMARKS["performance"]},
        {"factor": "Quality", "yours": k["quality"], "world-class": oee.BENCHMARKS["quality"]},
    ]
).set_index("factor")
st.bar_chart(bench_rows)
st.dataframe(
    bench_rows.assign(
        yours=lambda x: x["yours"].map(pct),
        **{"world-class": lambda x: x["world-class"].map(pct)},
    ),
    width="stretch",
)

left, right = st.columns(2)

# ----- where the planned time went
with left:
    st.subheader("Where the planned time went")
    loss = oee.loss_breakdown(df)
    st.bar_chart(loss.set_index("category")["minutes"])
    st.dataframe(
        loss.assign(hours=lambda x: (x["minutes"] / 60).round(1), share=lambda x: x["pct_of_planned"].map(pct))
        [["category", "hours", "share"]],
        width="stretch",
        hide_index=True,
    )

# ----- downtime pareto
with right:
    st.subheader("Downtime by reason")
    pareto = oee.downtime_pareto(df)
    if len(pareto):
        st.bar_chart(pareto.set_index("reason")["minutes"])
        st.dataframe(pareto, width="stretch", hide_index=True)
    else:
        st.write("No downtime recorded in this selection.")

# ----- machines and shifts
st.subheader("Machines")
mach = oee.summarize(df, "machine_id").sort_values("oee", ascending=False)
st.dataframe(
    mach.assign(**{f: mach[f].map(pct) for f in ["oee", "availability", "performance", "quality"]})
    [["machine_id", "oee", "availability", "performance", "quality"]],
    width="stretch",
    hide_index=True,
)

if df["shift"].nunique() > 1:
    st.subheader("Shifts")
    sh = oee.summarize(df, "shift").sort_values("oee", ascending=False)
    st.dataframe(
        sh.assign(**{f: sh[f].map(pct) for f in ["oee", "availability", "performance", "quality"]})
        [["shift", "oee", "availability", "performance", "quality"]],
        width="stretch",
        hide_index=True,
    )

# ----- download
st.subheader("Download")
summary = oee.summarize(df, ["machine_id", "shift"]).round(4)
st.download_button(
    "Download machine and shift summary (CSV)",
    summary.to_csv(index=False),
    file_name="oee_summary.csv",
    mime="text/csv",
)

ui.footer()
