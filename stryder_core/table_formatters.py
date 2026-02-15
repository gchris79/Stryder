import pandas as pd
from stryder_core import runtime_context
from stryder_core.date_utilities import dt_to_string
from stryder_core.runtime_context import get_tzinfo
from stryder_core.utils_formatting import fmt_hms, fmt_str_decimals, format_seconds


def format_view_columns(rows, mode, metrics = None):
    """Format runs (list of tuples) table for printing"""
    from stryder_core.utils import get_keys

    tz = get_tzinfo()
    headers = None

    formatted_rows= []
    for row in rows:
        # Header and data column order
        if mode == "for_views":
            headers = get_keys(["id", "dt", "wt_name", "distance", "duration", "power_avg", "avg_hr", "wt_type"])
            dt_obj = metrics["dt"]["formatter"](row["datetime"])
            display = [
                row["run_id"],
                dt_to_string(dt_obj, "ymd_hms", tz=tz),
                row["wt_name"],
                metrics["distance"]["formatter"](row["distance_m"]),
                metrics["duration"]["formatter"](row["duration_sec"]),
                metrics["power_avg"]["formatter"](row["avg_power"]),
                row["avg_hr"],
                row["wt_type"]
            ]
        elif mode == "for_report":
            headers = get_keys(["id", "dt", "wt_name", "duration", "distance"])
            dt_obj = metrics["dt"]["formatter"](row["datetime"])
            display = [
                row["run_id"],  # keep run_id here
                dt_to_string(dt_obj, "ymd_hms", tz=tz),
                row["wt_name"],
                metrics["duration"]["formatter"](row["duration"]),
                metrics["distance"]["formatter"](row["distance_m"]),
            ]
        else:
            display = [row[k] for k in row.keys()]  # fallback

        formatted_rows.append(display)

    return headers, formatted_rows


def weekly_table_fmt(weekly_raw:pd.DataFrame, metrics:dict) -> pd.DataFrame:
    """ Build a display-only weekly table using labels from metrics. Does NOT mutate the input df. """

    out = weekly_raw.copy()

    # Ensure that columns returned as numeric
    for col in ("distance_km", "duration_sec", "avg_power", "avg_hr", "runs"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["Week Start"] = out["week_start"].dt.strftime("%Y-%m-%d")
    out["Week End"] = out["week_end"].dt.strftime("%Y-%m-%d")

    cols = ["Week Start", "Week End"]

    # Runs
    if "runs" in out.columns and "Runs" not in out.columns:
        out["Runs"] = out["runs"]
    if "Runs" in out.columns:
        cols.append("Runs")

    # Distance
    if "distance_km" in out.columns:
        label = f'{metrics["distance"]["label"]} ({metrics["distance"]["unit"]})' if metrics["distance"].get("unit") else metrics["distance"]["label"]
        out[label] = out["distance_km"].round(2)
        cols.append(label)

    # Duration -> H:MM
    if "duration_sec" in out.columns:
        label = metrics["duration"]["label"]
        out[label] = out["duration_sec"].apply(fmt_hms)
        cols.append(label)

    # Power
    if "avg_power" in out.columns:
        spec = metrics["power_avg"]
        lbl = f'{spec["label"]} ({spec["unit"]})' if spec.get("unit") else spec["label"]
        out[lbl] = out["avg_power"]
        cols.append(lbl)

    # HR
    if "avg_hr" in out.columns:
        spec = metrics["avg_hr"]
        lbl = f'{spec["label"]} ({spec["unit"]})' if spec.get("unit") else spec["label"]
        out[lbl] = out["avg_hr"]
        cols.append(lbl)

    return out[cols]


def format_row_for_ui(row_dict, metrics) -> dict:
    """ Format dashboard run dict row for UI printing """
    # Convert raw DB value -> datetime object using the same formatter as CLI
    dt_obj = metrics["dt"]["formatter"](row_dict["datetime"])

    # Get tzinfo from runtime_context (assuming you've already set it somewhere)
    tzinfo = runtime_context.get_tzinfo()

    return {
        "run_id" : row_dict["run_id"],
        "dt": dt_to_string(dt_obj, "ymd", tz=tzinfo),
        "distance": metrics["distance"]["formatter"](row_dict["distance_m"]),
        "duration": metrics["duration"]["formatter"](row_dict["duration_sec"]),
        "avg_power": metrics["power_avg"]["formatter"](row_dict["avg_power"]),
        "avg_hr": row_dict["avg_hr"],
        "wt_name": row_dict["wt_name"],
        "wt_type": row_dict["wt_type"],
    }


def format_runs_summary_for_ui(summary_row: dict) -> dict:
    """ Format dashboard summary dict row for UI printing """
    if summary_row is None:
        return None

    return {
        "runs": summary_row["runs"],
        "distance": fmt_str_decimals(summary_row["distance_km"]),
        "duration": format_seconds(summary_row["duration_sec"]),
        "avg_power": fmt_str_decimals(summary_row["avg_power"]) if summary_row["avg_power"] is not None else "–",
        "avg_hr": fmt_str_decimals(summary_row["avg_hr"]) if summary_row["avg_hr"] is not None else "–",
    }