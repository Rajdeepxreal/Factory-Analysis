"""Machining Cost Calculator page. Run the project with: streamlit run home.py"""

from dataclasses import replace

import pandas as pd
import streamlit as st

import machining as mc
import ui

st.set_page_config(page_title="Machining Cost", page_icon="⚙️", layout="wide")
ui.inject_css()
ui.page_header(
    "⚙️",
    "Machining Cost Calculator",
    "Estimate cycle time and cost per part before you quote a job: turning, milling or drilling.",
    tag="Quoting",
)

left, mid, right = st.columns(3, gap="large")
with left:
    st.subheader("Job")
    operation = st.selectbox("Operation", mc.OPERATIONS)
    material = st.selectbox("Material", list(mc.MATERIALS))
    diameter = st.number_input("Diameter (mm)", min_value=0.1, value=50.0, step=1.0,
                               help="Workpiece diameter for turning, cutter diameter for milling, drill diameter for drilling.")
    length = st.number_input("Cut length or hole depth (mm)", min_value=0.1, value=100.0)
    removal = st.number_input("Depth to remove (mm)", min_value=0.0, value=5.0,
                              disabled=operation == "Drilling",
                              help="Turning: radial stock to remove. Milling: axial depth to mill.")
    depth = st.number_input("Depth per pass (mm)", min_value=0.1, value=2.5,
                            disabled=operation == "Drilling")

with mid:
    st.subheader("Cutting data")
    vc = st.number_input(
        "Cutting speed Vc (m/min)", min_value=1.0, value=float(mc.MATERIALS[material]["vc"]),
        key=f"vc_{material}",
        help="Starting value for the chosen material. Replace it with your tool catalogue's value.",
    )
    feed = st.number_input(
        "Feed (mm/rev, or mm/tooth for milling)", min_value=0.01, value=0.20, step=0.01,
    )
    teeth = st.number_input("Cutter teeth", min_value=1, value=4, disabled=operation != "Milling")
    st.subheader("Raw material")
    blank_d = st.number_input("Blank diameter (mm)", min_value=1.0, value=60.0)
    blank_l = st.number_input("Blank length (mm)", min_value=1.0, value=110.0)

with right:
    st.subheader("Economics")
    rate = st.number_input("Machine rate (₹ per hour)", min_value=0.0, value=1200.0, step=50.0)
    setup = st.number_input("Setup time (min)", min_value=0.0, value=30.0)
    batch = st.number_input("Batch size (parts)", min_value=1, value=50)
    tool_cost = st.number_input("Tool or insert cost (₹)", min_value=0.0, value=400.0)
    tool_life = st.number_input("Tool life (cutting minutes)", min_value=1.0, value=30.0)
    price = st.number_input(
        "Material price (₹ per kg)", min_value=0.0, value=float(mc.MATERIALS[material]["price_per_kg"]),
        key=f"price_{material}",
        help="Approximate. Use your supplier's current price.",
    )

job = mc.Job(
    operation=operation, material=material, diameter_mm=diameter, length_mm=length,
    removal_mm=removal, depth_per_pass_mm=depth, cutting_speed=vc, feed=feed, teeth=int(teeth),
    blank_diameter_mm=blank_d, blank_length_mm=blank_l, machine_rate=rate, setup_min=setup,
    batch_size=int(batch), tool_cost=tool_cost, tool_life_min=tool_life, price_per_kg=price,
)

try:
    timing = mc.cycle_time(job)
except ValueError as e:
    st.error(str(e))
    st.stop()

costs = mc.cost(job, timing)

st.subheader("Result")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cycle time", f"{timing['cycle_min']:.2f} min")
k2.metric("Spindle speed", f"{timing['rpm']:,.0f} rpm")
k3.metric("Feed rate", f"{timing['feed_mm_min']:,.0f} mm/min")
k4.metric("Cost per part", f"₹ {costs['per_part']:,.2f}")
k5.metric("Cost per batch", f"₹ {costs['per_batch']:,.0f}")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.subheader("Where the cost goes")
    breakdown = pd.Series(costs["parts"], name="₹ per part")
    st.bar_chart(breakdown)
    st.dataframe(
        breakdown.round(2).rename_axis("Item").reset_index(),
        width="stretch", hide_index=True,
    )
with c2:
    st.subheader("Cycle time vs cutting speed")
    speeds = [round(vc * f, 1) for f in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5)]
    cycles = mc.cycle_vs_speed(job, speeds)
    curve = pd.DataFrame({"Cycle time (min)": cycles}, index=pd.Index(speeds, name="Cutting speed (m/min)"))
    st.line_chart(curve)
    st.caption("Faster cutting shortens the cycle but wears the tool sooner. Compare the tool cost line above.")

with st.expander("How the numbers are calculated"):
    st.latex(r"N = \frac{1000\, v_c}{\pi D}")
    st.latex(r"f_m = f \cdot N \quad \text{(turning, drilling)}")
    st.latex(r"f_m = f_z \cdot z \cdot N \quad \text{(milling)}")
    st.latex(r"t_{cycle} = \frac{\text{passes} \times \text{travel}}{f_m}")
    st.markdown(
        "Cost per part = material + machine time + tool wear + setup share. Tool wear is the tool "
        "cost multiplied by the share of its life used by this cycle."
    )
st.caption(
    "Estimates for quoting only. Confirm cutting data with your tool supplier and measure real "
    "cycle times before you commit to a price."
)
ui.footer()
