"""Machining time and cost for one part.

Standard shop-floor approximations for estimating and quoting. Confirm cutting data with the
tool supplier's catalogue for your exact tool and material, and measure real cycle times.
"""

import math
from dataclasses import dataclass

OPERATIONS = ("Turning", "Milling", "Drilling")

# density (g/cm3), starting cutting speed Vc for carbide turning (m/min), approximate price (INR/kg)
MATERIALS = {
    "Mild steel": {"density": 7.85, "vc": 150.0, "price_per_kg": 90.0},
    "Stainless steel": {"density": 8.00, "vc": 90.0, "price_per_kg": 320.0},
    "Cast iron": {"density": 7.20, "vc": 120.0, "price_per_kg": 75.0},
    "Aluminium": {"density": 2.70, "vc": 400.0, "price_per_kg": 240.0},
    "Brass": {"density": 8.50, "vc": 250.0, "price_per_kg": 700.0},
}

APPROACH_MM = 2.0          # extra travel at the start of a turning pass
DRILL_TIP_FACTOR = 0.3     # extra drill travel, as a multiple of the drill diameter


@dataclass
class Job:
    operation: str
    material: str
    diameter_mm: float        # workpiece (turning), cutter (milling) or drill (drilling) diameter
    length_mm: float          # cut length (turning, milling) or hole depth (drilling)
    removal_mm: float         # total depth to remove (turning: radial, milling: axial)
    depth_per_pass_mm: float  # depth of cut per pass
    cutting_speed: float      # Vc in m/min
    feed: float               # mm/rev (turning, drilling) or mm/tooth (milling)
    teeth: int                # milling only
    blank_diameter_mm: float
    blank_length_mm: float
    machine_rate: float       # per hour
    setup_min: float
    batch_size: int
    tool_cost: float          # cost of one tool or insert
    tool_life_min: float      # cutting minutes one tool lasts
    price_per_kg: float


def cycle_time(job: Job) -> dict:
    """Spindle speed, feed rate, number of passes and cycle time for one part."""
    if job.operation not in OPERATIONS:
        raise ValueError(f"Unknown operation: {job.operation}")
    if job.diameter_mm <= 0 or job.cutting_speed <= 0 or job.feed <= 0:
        raise ValueError("Diameter, cutting speed and feed must be above zero.")

    rpm = 1000 * job.cutting_speed / (math.pi * job.diameter_mm)

    if job.operation == "Turning":
        if job.depth_per_pass_mm <= 0:
            raise ValueError("Depth per pass must be above zero.")
        feed_mm_min = job.feed * rpm
        passes = math.ceil(job.removal_mm / job.depth_per_pass_mm) if job.removal_mm > 0 else 1
        travel = job.length_mm + APPROACH_MM
    elif job.operation == "Milling":
        if job.depth_per_pass_mm <= 0 or job.teeth < 1:
            raise ValueError("Depth per pass must be above zero and the cutter needs at least one tooth.")
        feed_mm_min = job.feed * job.teeth * rpm
        passes = math.ceil(job.removal_mm / job.depth_per_pass_mm) if job.removal_mm > 0 else 1
        travel = job.length_mm + job.diameter_mm
    else:  # Drilling
        feed_mm_min = job.feed * rpm
        passes = 1
        travel = job.length_mm + DRILL_TIP_FACTOR * job.diameter_mm

    cycle_min = passes * travel / feed_mm_min
    return {
        "rpm": rpm,
        "feed_mm_min": feed_mm_min,
        "passes": passes,
        "travel_mm": travel,
        "cycle_min": cycle_min,
    }


def cost(job: Job, timing: dict) -> dict:
    """Cost of one part, split into its parts, and the cost of the whole batch."""
    minute_rate = job.machine_rate / 60
    volume_cm3 = math.pi / 4 * job.blank_diameter_mm ** 2 * job.blank_length_mm / 1000
    kg = volume_cm3 * MATERIALS[job.material]["density"] / 1000

    parts = {
        "Material": kg * job.price_per_kg,
        "Machine time": timing["cycle_min"] * minute_rate,
        "Tools": job.tool_cost * timing["cycle_min"] / job.tool_life_min,
        "Setup (share per part)": job.setup_min * minute_rate / job.batch_size,
    }
    per_part = sum(parts.values())
    return {"parts": parts, "per_part": per_part, "per_batch": per_part * job.batch_size}


def cycle_vs_speed(job: Job, speeds: list[float]) -> list[float]:
    """Cycle time (min) at each cutting speed, to show the trade-off between speed and tool life."""
    from dataclasses import replace
    return [cycle_time(replace(job, cutting_speed=s))["cycle_min"] for s in speeds]
