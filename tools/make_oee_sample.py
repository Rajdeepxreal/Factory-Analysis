"""Generates sample_data.csv: a fake but realistic production log for demo purposes.

The data has built-in problems for the dashboard to discover:
    LATHE-01 : lots of breakdowns (low availability)
    PRESS-01 : runs slower than its ideal cycle time (low performance)
    CNC-02   : high scrap on the night shift C (low quality, only on that shift)
    PACK-01  : long changeovers, and it only runs shifts A and B
"""
from pathlib import Path
import random

import pandas as pd

random.seed(7)

PLANNED = 450  # minutes per 8 h shift after a 30 min break

# ideal cycle time (s), mean availability, mean performance, mean quality, downtime reason weights
MACHINES = {
    "CNC-01": dict(ideal=30, avail=0.92, perf=0.96, qual=0.985,
                   reasons={"Tool change": 4, "Breakdown": 2, "Material shortage": 2, "Minor stops": 2}),
    "CNC-02": dict(ideal=32, avail=0.93, perf=0.95, qual=0.985,
                   reasons={"Tool change": 4, "Breakdown": 2, "Material shortage": 1, "Minor stops": 3}),
    "LATHE-01": dict(ideal=24, avail=0.78, perf=0.94, qual=0.985,
                     reasons={"Breakdown": 7, "Tool change": 2, "Operator absent": 1}),
    "PRESS-01": dict(ideal=12, avail=0.91, perf=0.82, qual=0.99,
                     reasons={"Changeover": 3, "Breakdown": 2, "Minor stops": 4, "Material shortage": 1}),
    "PACK-01": dict(ideal=6, avail=0.88, perf=0.93, qual=0.995,
                    shifts=["A", "B"],
                    reasons={"Changeover": 8, "Material shortage": 3, "Minor stops": 2}),
}
SHIFTS = ["A", "B", "C"]
QUALITY_OVERRIDE = {("CNC-02", "C"): 0.87}

rows = []
for day in pd.date_range("2026-08-03", "2026-10-31"):
    if day.dayofweek == 6:  # no production on Sundays
        continue
    for machine, cfg in MACHINES.items():
        for shift in cfg.get("shifts", SHIFTS):
            avail = min(1.0, max(0.5, random.gauss(cfg["avail"], 0.05)))
            downtime = round(PLANNED * (1 - avail))
            reason = ""
            if downtime > 0 and random.random() > 0.08:  # a few shifts have no recorded reason
                reasons, weights = zip(*cfg["reasons"].items())
                reason = random.choices(reasons, weights)[0]
            elif downtime > 0:
                downtime = 0
            run = PLANNED - downtime
            perf = min(0.99, max(0.6, random.gauss(cfg["perf"], 0.03)))
            total = int(run * 60 / cfg["ideal"] * perf)
            qual = QUALITY_OVERRIDE.get((machine, shift), cfg["qual"])
            qual = min(1.0, max(0.8, random.gauss(qual, 0.01)))
            good = total - round(total * (1 - qual))
            rows.append({
                "date": day.strftime("%Y-%m-%d"), "shift": shift, "machine_id": machine,
                "planned_time_min": PLANNED, "downtime_min": downtime, "downtime_reason": reason,
                "ideal_cycle_time_sec": cfg["ideal"], "total_count": total, "good_count": good,
            })

pd.DataFrame(rows).to_csv(Path(__file__).resolve().parent.parent / "sample_oee.csv", index=False)
print(len(rows), "rows written")
