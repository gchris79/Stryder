import math
import pandas as pd
from typing import Literal
from stryder_core.date_utilities import dt_to_string
from stryder_core.runtime_context import get_tzinfo


""" fmt_pace is the core function and fmt_pace_km and fmt_pace_no_unit wrapper functions for picking the mode """
def fmt_pace_km(seconds):
    return fmt_pace(seconds, with_unit=True)

def fmt_pace_no_unit(seconds):
    return fmt_pace(seconds, with_unit=False)

def fmt_pace(seconds: float | int | None, with_unit: bool = False) -> str:
    """ Takes seconds and returns pace in mm/ss or mm/ss/km format """
    # Validate input
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(sec) or sec <= 0:
        return ""
    # Convert and format
    sec = int(round(sec))
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}" if not with_unit else f"{m}:{s:02d}/km"


def fmt_str_decimals(fl_num) -> str:
    """ Format string decimal numbers, returns formatted string """
    fmt_num = "{:.2f}".format(fl_num)
    return fmt_num


def fmt_distance(meters) -> float:
    """ Calculates km from meters """
    km = float(meters / 1000)
    return km


""" format_seconds is the core function and fmt_hms and fmt_hm wrapper functions for picking the mode """
def fmt_hms(seconds):
    return format_seconds(seconds,'hms')

def fmt_hm(seconds):
    return format_seconds(seconds,'hm')

def format_seconds(
    seconds,
    mode:Literal["hms","hm"] = "hm",
):
    """ Takes seconds and returns time in hms or hm format """
    # Check for undesirable values normalizing to 0
    try:
        total_sec = float(seconds)
    except (TypeError, ValueError):
        total_sec = 0
    if math.isnan(total_sec):
        total_sec = 0
    if total_sec < 0:
        total_sec = 0
    # Round to nearest second
    sec = max(0, int(round(total_sec)))

    # Format to time
    h, rem = divmod(sec, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02}:{m:02}" if mode == "hm" else f"{h:02}:{m:02}:{s:02}"


def format_view_columns(rows, mode, metrics = None):
    """Format runs (list of tuples) table for printing"""
    from stryder_core.utils import get_keys

    tz = get_tzinfo()
    headers = None

    formatted_rows= []
    for row in rows:
        # Header and data column order
        if mode == "for_views":
            headers = get_keys(["dt", "wt_name", "distance", "duration", "power_avg", "HR", "wt_type"])
            dt_obj = metrics["dt"]["formatter"](row["datetime"])
            display = [
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

    out["Week Start"] = out["week_start"].dt.strftime("%Y-%m-%d")
    out["Week End"] = out["week_end"].dt.strftime("%Y-%m-%d")

    cols = []
    # Runs
    if "runs" in out.columns and "Runs" not in out.columns:
        out["Runs"] = out["runs"]
    if "Runs" in out.columns:
        cols.append("Runs")

    # Distance
    if "distance_km" in out:
        label = f'{metrics["distance"]["label"]} ({metrics["distance"]["unit"]})' if metrics["distance"].get("unit") else metrics["distance"]["label"]
        out[label] = out["distance_km"].round(2)
        cols.append(label)

    # Duration -> H:MM
    if "duration_sec" in out:
        label = metrics["duration"]["label"]
        out[label] = out["duration_sec"].apply(fmt_hms)
        cols.append(label)

    # Power
    if "avg_power" in out:
        spec = metrics["power_avg"]
        lbl = f'{spec["label"]} ({spec["unit"]})' if spec.get("unit") else spec["label"]
        out[lbl] = out["avg_power"]
        cols.append(lbl)

    # HR
    if "avg_hr" in out:
        spec = metrics["HR"]
        lbl = f'{spec["label"]} ({spec["unit"]})' if spec.get("unit") else spec["label"]
        out[lbl] = out["avg_hr"]
        cols.append(lbl)

    return out[cols]