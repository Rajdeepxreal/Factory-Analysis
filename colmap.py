"""Match a user's CSV headers to the column names the analysis needs."""

import re

import pandas as pd

# Common names used in factory exports for each column the analysis needs
ALIASES = {
    "date": ["day", "production_date", "breakdown_date", "failure_date", "event_date", "timestamp"],
    "machine_id": ["machine", "machine_name", "machine_code", "asset", "asset_id", "equipment",
                   "equipment_id", "work_centre", "workcenter", "line"],
    "failure_type": ["failure", "failure_mode", "fault", "fault_type", "cause", "breakdown_type", "problem"],
    "downtime_hours": ["downtime_h", "downtime_hrs", "repair_hours", "hours_down", "outage_hours", "hours"],
    "repair_cost": ["cost", "maintenance_cost", "total_cost", "spares_cost"],
    "technician": ["engineer", "mechanic", "done_by", "assigned_to"],
    "shift": ["shift_name", "shift_id"],
    "planned_time_min": ["planned_time", "planned_minutes", "scheduled_time", "planned_min"],
    "downtime_min": ["downtime_minutes", "stop_minutes", "down_min", "stopped_min"],
    "downtime_reason": ["stop_reason", "reason", "loss_reason", "cause_of_stop"],
    "ideal_cycle_time_sec": ["ideal_cycle_time", "cycle_time_sec", "ct_sec", "std_cycle_time"],
    "total_count": ["total_parts", "parts_made", "produced", "output", "total_produced"],
    "good_count": ["good_parts", "good", "parts_good", "accepted"],
}

NOT_IN_FILE = "(not in my file)"


def normalise(name) -> str:
    """'Machine ID ', 'machine-id' and 'MACHINE_ID' all become 'machine_id'."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def read_columns(source) -> list[str]:
    """Header names of a CSV path or uploaded file, normalised. Empty list if unreadable."""
    if hasattr(source, "seek"):
        source.seek(0)
    try:
        cols = list(pd.read_csv(source, nrows=0).columns)
    except Exception:  # noqa: BLE001
        cols = []
    if hasattr(source, "seek"):
        source.seek(0)
    return [normalise(c) for c in cols]


def suggest(columns: list[str], wanted: list[str]) -> dict:
    """For each wanted column, the file column that best matches it (or None). Each file column is used once."""
    used, result = set(), {}
    for canon in wanted:
        result[canon] = None
        for candidate in [canon] + ALIASES.get(canon, []):
            if candidate in columns and candidate not in used:
                result[canon] = candidate
                used.add(candidate)
                break
    return result


def apply_mapping(df: pd.DataFrame, mapping: dict | None) -> pd.DataFrame:
    """Normalise the headers and rename matched columns to the names the analysis uses."""
    df = df.copy()
    df.columns = [normalise(c) for c in df.columns]
    if not mapping:
        return df
    # If the file already has a column named like the target but the user chose another, drop it
    clash = [canon for canon, src in mapping.items() if src and canon in df.columns and src != canon]
    df = df.drop(columns=clash)
    rename = {src: canon for canon, src in mapping.items() if src and src in df.columns}
    return df.rename(columns=rename)
