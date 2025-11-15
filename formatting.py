import math
import pandas as pd
from typing import Literal
from date_utilities import dt_to_string
from runtime_context import get_tzinfo
from utils import fmt_sec_to_hms



def fmt_hms_df(sec, pos=None, mode:Literal["hms","hm"] = "hm" ) -> str:
    sec = max(0, int(round(sec)))
    h, rem = divmod(sec, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02}:{m:02}" if mode == "hm" else f"{h:02}:{m:02}:{s:02}"


def fmt_pace_df(sec_per_km, pos=None) -> str:
    if sec_per_km is None or not math.isfinite(sec_per_km) or sec_per_km <= 0:
        return ""
    m, s = divmod(int(round(sec_per_km)), 60)
    return f"{m}:{s:02d}"  # axis label should carry "(min/km)"


def format_view_columns(rows, mode, columns, metrics = None):
    """Format runs (list of tuples) table for printing"""
    from utils import get_keys

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
        out[label] = out["duration_sec"].apply(fmt_sec_to_hms)
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
