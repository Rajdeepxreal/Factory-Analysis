"""OEE (Overall Equipment Effectiveness) calculations.

OEE = Availability x Performance x Quality

    Availability = run time / planned time                  (losses: breakdowns, changeovers, waiting)
    Performance  = ideal time for the parts made / run time (losses: slow cycles, micro-stops)
    Quality      = ideal time of the good parts / ideal time of all parts (losses: scrap, rework)

Quality is weighted by ideal cycle time, so products with different speeds combine correctly and
OEE equals A x P x Q exactly at every level (machine, shift, week, whole plant). Percentages are
never averaged: the underlying minutes and counts are summed first, then the ratios are taken.

Expected CSV columns (one row per machine per shift or production run):
    date                  - day of production (DD-MM-YYYY or YYYY-MM-DD)
    machine_id            - e.g. CNC-01
    planned_time_min      - minutes the machine was planned to produce
    downtime_min          - minutes it stood still during that time
    ideal_cycle_time_sec  - fastest realistic seconds per part
    total_count           - all parts made (good + rejected)
    good_count            - parts that passed inspection
Optional:
    shift                 - e.g. A, B, C
    downtime_reason       - main reason for the downtime, e.g. Breakdown
"""

import pandas as pd

import colmap

REQUIRED_COLUMNS = [
    "date", "machine_id", "planned_time_min", "downtime_min",
    "ideal_cycle_time_sec", "total_count", "good_count",
]
OPTIONAL_COLUMNS = ["shift", "downtime_reason"]
NUMBER_COLUMNS = ["planned_time_min", "downtime_min", "ideal_cycle_time_sec", "total_count", "good_count"]

# Commonly quoted "world class" levels for OEE and its three factors
BENCHMARKS = {"oee": 0.85, "availability": 0.90, "performance": 0.95, "quality": 0.99}
FACTORS = ("availability", "performance", "quality")

FACTOR_ADVICE = {
    "availability": "Machines are standing still too often. Work through the downtime Pareto: "
                    "breakdowns, changeovers, waiting for material or people.",
    "performance": "Machines run slower than their ideal cycle time. Look for micro-stops, worn "
                   "tooling, conservative feed/speed settings and slow starts after changeovers.",
    "quality": "Too many parts are rejected or reworked. Check setup approval, tool wear, "
               "material variation and inspection feedback to the operator.",
}

# Sum these columns first, then take ratios (never average percentages)
_SUM_COLUMNS = {
    "planned_min": "planned_time_min",
    "downtime_min": "downtime_min",
    "run_min": "run_min",
    "ideal_min": "ideal_min",
    "good_min": "good_min",
    "total_count": "total_count",
    "good_count": "good_count",
}


# Summary format: one row per machine per shift, with hours and percentages already calculated
SUMMARY_REQUIRED = ["date", "machine_id", "planned_hours", "actual_hours", "availability_pct",
                    "performance_pct", "quality_pct", "units_produced", "defects"]
SUMMARY_OPTIONAL = ["shift", "oee_pct"]


def _is_summary(columns) -> bool:
    cols = set(columns)
    return "planned_hours" in cols or "performance_pct" in cols


def columns_for(source) -> tuple:
    """(required, optional) column names for this file, so the page checks the right ones."""
    cols = colmap.read_columns(source)
    if _is_summary(cols):
        return SUMMARY_REQUIRED, SUMMARY_OPTIONAL
    return REQUIRED_COLUMNS, OPTIONAL_COLUMNS


def _from_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Turn a summary file into the minute-and-count columns used everywhere else.

    The conversion reproduces the file's own numbers: availability from the hours, performance
    from the ideal cycle time, and quality from the defect count.
    """
    missing = [c for c in SUMMARY_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    out = df.copy()
    for c in ["planned_hours", "actual_hours", "performance_pct", "units_produced", "defects", "oee_pct"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    out["planned_time_min"] = out["planned_hours"] * 60
    out["downtime_min"] = (out["planned_hours"] - out["actual_hours"]) * 60
    run_min = out["actual_hours"] * 60
    out["total_count"] = out["units_produced"]
    out["good_count"] = out["units_produced"] - out["defects"]
    ideal_cycle = out["performance_pct"] * run_min * 60 / out["units_produced"]
    out["ideal_cycle_time_sec"] = ideal_cycle.where(out["units_produced"] > 0)
    return out


# --------------------------------------------------------------------------- loading

def _parse_dates(raw: pd.Series) -> pd.Series:
    """Parse dates: YYYY-MM-DD, or day-first formats such as 14-03-2026 and 14/03/2026."""
    text = raw.astype(str).str.strip()
    parsed = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    rest = parsed.isna()
    if rest.any():
        parsed[rest] = pd.to_datetime(text[rest], dayfirst=True, format="mixed", errors="coerce")
    return parsed


def _date_message(raw: str) -> str:
    hint = (
        " (Excel shows ######## when a column is too narrow: widen the column, "
        "then save the CSV again)"
        if raw.startswith("#")
        else ""
    )
    return f"date '{raw}' is not a valid date{hint}"


def load_log(file, mapping=None) -> pd.DataFrame:
    """Read and validate a production log.

    Rows with unusable data are left out, and the reason for each is stored in
    df.attrs["skipped_rows"] so the app can show them instead of dropping them silently.
    Suspicious but usable rows are listed in df.attrs["warnings"].
    """
    df = colmap.apply_mapping(pd.read_csv(file), mapping)
    if _is_summary(df.columns):
        df = _from_summary(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    raw = df[["date"] + NUMBER_COLUMNS].astype(str).apply(lambda s: s.str.strip()).replace("nan", "(blank)")

    df["date"] = _parse_dates(df["date"])
    for col in NUMBER_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["machine_id"] = df["machine_id"].astype("string").str.strip().str.upper().replace("", pd.NA)
    if "shift" in df.columns:
        df["shift"] = df["shift"].astype("string").str.strip().str.title().replace("", pd.NA).fillna("All")
    else:
        df["shift"] = "All"
    if "downtime_reason" in df.columns:
        df["downtime_reason"] = (
            df["downtime_reason"].astype("string").str.strip().str.capitalize().replace("", pd.NA)
        )
    else:
        df["downtime_reason"] = pd.NA

    p, d = df["planned_time_min"], df["downtime_min"]
    c, t, g = df["ideal_cycle_time_sec"], df["total_count"], df["good_count"]

    def val(col, i):
        return raw.at[i, col]

    checks = [
        (df["date"].isna(), lambda i: _date_message(val("date", i))),
        (df["machine_id"].isna(), lambda i: "machine_id is empty"),
        (~(p > 0), lambda i: f"planned_time_min '{val('planned_time_min', i)}' must be a number above 0"),
        (~(d >= 0), lambda i: f"downtime_min '{val('downtime_min', i)}' must be a number, 0 or more"),
        (d > p, lambda i: f"downtime_min ({val('downtime_min', i)}) is more than "
                          f"planned_time_min ({val('planned_time_min', i)})"),
        (~(c > 0), lambda i: f"ideal_cycle_time_sec '{val('ideal_cycle_time_sec', i)}' must be a number above 0"),
        (~(t >= 0), lambda i: f"total_count '{val('total_count', i)}' must be a number, 0 or more"),
        (~(g >= 0), lambda i: f"good_count '{val('good_count', i)}' must be a number, 0 or more"),
        (g > t, lambda i: f"good_count ({val('good_count', i)}) is more than total_count ({val('total_count', i)})"),
        ((p > 0) & (d == p) & (t > 0), lambda i: "machine was down for the whole planned time, yet parts were counted"),
    ]
    bad = pd.concat([mask for mask, _ in checks], axis=1).any(axis=1)

    skipped = []
    for idx in df.index[bad]:
        why = [message(idx) for mask, message in checks if mask[idx]]
        skipped.append({"row": int(idx) + 2, "problem": "; ".join(why)})  # +2: header line, 1-based

    out = df[~bad].copy()
    out["source_row"] = out.index + 2
    out["machine_id"] = out["machine_id"].astype(object)
    out["shift"] = out["shift"].astype(object)
    out["downtime_reason"] = out["downtime_reason"].astype(object)
    unlabeled = (out["downtime_min"] > 0) & out["downtime_reason"].isna()
    out.loc[unlabeled, "downtime_reason"] = "Unspecified"

    # Time bookkeeping in minutes
    out["run_min"] = out["planned_time_min"] - out["downtime_min"]
    out["ideal_min"] = out["ideal_cycle_time_sec"] * out["total_count"] / 60
    out["good_min"] = out["ideal_cycle_time_sec"] * out["good_count"] / 60

    out = out.sort_values(["date", "machine_id", "shift"]).reset_index(drop=True)

    warnings = []
    if "oee_pct" in out.columns:
        computed = out["good_min"] / out["planned_time_min"]
        off = out[(computed - out["oee_pct"]).abs() > 0.01]
        if len(off):
            warnings.append(
                f"{len(off)} row(s) have an OEE that differs from availability x performance x "
                "quality by more than 1 point. Check those rows."
            )
    too_fast = out[out["ideal_min"] > out["run_min"] * 1.0001]
    if len(too_fast):
        rows = ", ".join(str(r) for r in too_fast["source_row"].head(8))
        more = "..." if len(too_fast) > 8 else ""
        warnings.append(
            f"{len(too_fast)} row(s) show performance above 100% (rows {rows}{more}). "
            "The ideal cycle time may be set too slow, or the part counts too high. "
            "Their OEE can look better than reality."
        )
    out.attrs["skipped_rows"] = skipped
    out.attrs["warnings"] = warnings
    return out


# --------------------------------------------------------------------------- calculations

def _ratios(sums: pd.DataFrame) -> pd.DataFrame:
    out = sums.copy()
    out["availability"] = out["run_min"] / out["planned_min"]
    out["performance"] = (out["ideal_min"] / out["run_min"]).where(out["run_min"] > 0)
    out["quality"] = (out["good_min"] / out["ideal_min"]).where(out["ideal_min"] > 0)
    out["oee"] = out["good_min"] / out["planned_min"]
    return out


def summarize(df: pd.DataFrame, by=None) -> pd.DataFrame:
    """OEE and its three factors, overall (by=None) or grouped by one or more columns."""
    if by is None:
        sums = pd.DataFrame([{name: df[col].sum() for name, col in _SUM_COLUMNS.items()}])
    else:
        sums = df.groupby(by, as_index=False).agg(**{name: (col, "sum") for name, col in _SUM_COLUMNS.items()})
    return _ratios(sums)


def kpis(df: pd.DataFrame) -> dict:
    """Headline numbers for the whole selection."""
    return summarize(df).iloc[0].to_dict()


def trend(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """OEE per day ('D'), week ('W') or month ('M')."""
    d = df.copy()
    d["period"] = d["date"].dt.to_period(freq).dt.start_time
    return summarize(d, "period")


def loss_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Where the planned time went. The four categories add up to 100% of planned time."""
    k = kpis(df)
    rows = [
        ("Fully productive time", k["good_min"]),
        ("Quality loss", k["ideal_min"] - k["good_min"]),
        ("Speed loss", k["run_min"] - k["ideal_min"]),
        ("Downtime loss", k["downtime_min"]),
    ]
    out = pd.DataFrame(rows, columns=["category", "minutes"])
    out["pct_of_planned"] = out["minutes"] / k["planned_min"]
    return out


def downtime_pareto(df: pd.DataFrame) -> pd.DataFrame:
    """Downtime minutes by reason, largest first, with the cumulative share."""
    d = df[df["downtime_min"] > 0]
    if d.empty:
        return pd.DataFrame(columns=["reason", "minutes", "share_%", "cumulative_%"])
    out = (
        d.groupby("downtime_reason")["downtime_min"].sum()
        .sort_values(ascending=False)
        .rename_axis("reason")
        .reset_index(name="minutes")
    )
    out["share_%"] = (out["minutes"] / out["minutes"].sum() * 100).round(1)
    out["cumulative_%"] = out["share_%"].cumsum().round(1)
    return out


# --------------------------------------------------------------------------- advice

def _pct(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


def weakest_factor(row) -> tuple:
    """The factor furthest below its world-class level, and by how much (as a fraction)."""
    gaps = {f: BENCHMARKS[f] - row[f] for f in FACTORS if pd.notna(row[f])}
    if not gaps:
        return None, 0.0
    factor = max(gaps, key=gaps.get)
    return factor, gaps[factor]


def recommendations(df: pd.DataFrame, target: float = 0.85) -> list:
    """Plain-language findings that need no AI and no API key."""
    recs = []
    k = kpis(df)

    diff = (k["oee"] - target) * 100
    recs.append(
        f"OEE is {_pct(k['oee'])}, {abs(diff):.1f} points {'above' if diff >= 0 else 'below'} "
        f"your {target * 100:.0f}% target."
    )

    factor, gap = weakest_factor(k)
    if factor and gap > 0:
        recs.append(
            f"The biggest gap is **{factor}** at {_pct(k[factor])} (world-class is "
            f"{BENCHMARKS[factor] * 100:.0f}%). {FACTOR_ADVICE[factor]}"
        )
    else:
        recs.append("All three factors are at or above world-class levels. Keep monitoring for slips.")

    machines = summarize(df, "machine_id").sort_values("oee")
    if len(machines) > 1:
        worst = machines.iloc[0]
        f, _ = weakest_factor(worst)
        reason = f", held back mainly by {f} ({_pct(worst[f])})" if f else ""
        recs.append(f"**{worst['machine_id']}** has the lowest OEE ({_pct(worst['oee'])}){reason}.")

    pareto = downtime_pareto(df)
    if len(pareto) and set(pareto["reason"]) == {"Unspecified"}:
        recs.append(
            "This file has no downtime reasons, so the causes of downtime cannot be ranked. "
            "Add a downtime_reason column (for example Breakdown or Changeover) to find them."
        )
    elif len(pareto):
        top = pareto.iloc[0]
        recs.append(
            f"**{top['reason']}** is the largest downtime cause: {top['minutes'] / 60:.0f} h, "
            f"{top['share_%']:.0f}% of all downtime."
        )

    shifts = summarize(df, "shift").sort_values("oee")
    if len(shifts) > 1:
        lo, hi = shifts.iloc[0], shifts.iloc[-1]
        spread = (hi["oee"] - lo["oee"]) * 100
        if spread >= 3:
            recs.append(
                f"Shift **{lo['shift']}** runs at {_pct(lo['oee'])} against {_pct(hi['oee'])} on shift "
                f"{hi['shift']}, a {spread:.1f}-point gap. Compare how the two shifts work."
            )

    combos = summarize(df, ["machine_id", "shift"])
    machine_oee = machines.set_index("machine_id")["oee"]
    combos["below_machine"] = combos["machine_id"].map(machine_oee) - combos["oee"]
    spot = combos.sort_values("below_machine", ascending=False).iloc[0]
    if len(shifts) > 1 and spot["below_machine"] >= 0.05:
        f, _ = weakest_factor(spot)
        why = f" Its weakest factor is {f} ({_pct(spot[f])})." if f else ""
        recs.append(
            f"Hot spot: **{spot['machine_id']} on shift {spot['shift']}** runs at {_pct(spot['oee'])}, "
            f"{spot['below_machine'] * 100:.1f} points below the machine's own average.{why}"
        )

    span = (df["date"].max() - df["date"].min()).days
    if span >= 59:
        end = df["date"].max()
        recent = df[df["date"] > end - pd.Timedelta(days=30)]
        before = df[(df["date"] <= end - pd.Timedelta(days=30)) & (df["date"] > end - pd.Timedelta(days=60))]
        if len(recent) and len(before):
            change = (kpis(recent)["oee"] - kpis(before)["oee"]) * 100
            recs.append(
                f"Over the last 30 days OEE {'improved' if change >= 0 else 'dropped'} by "
                f"{abs(change):.1f} points compared with the 30 days before."
            )
    return recs
