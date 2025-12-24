from functools import partial
from typing import TypedDict, Literal, Callable, Any
import pandas as pd
from stryder_core.utils_formatting import fmt_hms, fmt_pace_km, fmt_str_decimals, fmt_distance_km_str
from stryder_core.runtime_context import get_tzinfo
from stryder_core.date_utilities import to_utc, as_aware


class MetricInfo(TypedDict, total=False):
    key: str
    label: str
    unit: str
    formatter: str | Callable[[Any], Any]

# This is the dictionary from which the metrics dict will be built, this is used after the db is created for reports, views etc. #
METRICS_SPEC : dict[str ,MetricInfo] = {
    "id":        {"key": "run_id",              "label": "Run ID",                          "formatter": "id"},
    "wt_name":   {"key": "wt_name",             "label": "Workout Name",                    "formatter": "wt_name"},
    "wt_type":   {"key": "wt_type",             "label": "Workout Type",                    "formatter": "wt_type"},
    "dt":        {"key": "datetime",            "label": "Datetime",                        "formatter" : "dt"},
    "power_sec": {"key": "power",               "label": "Power",         "unit": "W/kg",   "formatter": "power",   "plottable_single": True},
    "power_avg": {"key": "avg_power",           "label": "Avg Power",     "unit": "W/kg",   "formatter": "power"},
    "duration":  {"key": "duration_sec",        "label": "Duration",      "unit": "h:m",    "formatter": "duration"},
    "pace":      {"key": "pace",                "label": "Pace",          "unit": "min/km", "formatter": "pace"},
    "ground":    {"key": "ground_time",         "label": "Ground Time",   "unit": "ms",     "formatter": "ground",  "plottable_single": True},
    "lss":       {"key": "stiffness",           "label": "LSS",           "unit": "kN/m",   "formatter": "lss",     "plottable_single": True},
    "cadence":   {"key": "cadence",             "label": "Cadence",       "unit": "spm",    "formatter": "cadence", "plottable_single": True},
    "vo":        {"key": "vertical_oscillation","label": "Vert. Oscillation", "unit": "cm",     "formatter": "vo",      "plottable_single": True},
    "distance":  {"key": "distance_m",          "label": "Distance",      "unit": "m",      "formatter": "distance"},
    "distance_km":{"key": "distance_km",        "label": "Distance",      "unit": "km",      "formatter": "distance"},
    "avg_hr":    {"key": "avg_hr",              "label": "Avg HR",        "unit": "bpm",    "formatter": "avg_hr"}

}

# Canonical stream keys that will be used in file parsing #
STRYD_PARSE_SPEC = {
    "timestamp_s":        {"aliases": ["Timestamp"]},
    "str_dist_m":         {"aliases": ["Stryd Distance (meters)"]},
    "watch_dist_m":       {"aliases": ["Watch Distance (meters)"]},
    "str_speed":          {"aliases": ["Stryd Speed (m/s)"]},
    "watch_speed":        {"aliases": ["Watch Speed (m/s)"]},
    "power_sec":          {"aliases": ["Power (w/kg)"]},
    "form_power":         {"aliases": ["Form Power (w/kg)"]},
    "air_power":          {"aliases": ["Air Power (w/kg)"]},
    "ground":             {"aliases": ["Ground Time (ms)"]},
    "cadence":            {"aliases": ["Cadence (spm)"]},
    "vo":                 {"aliases": ["Vertical Oscillation (cm)"]},
    "watch_elev":         {"aliases": ["Watch Elevation (m)"]},
    "stryd_elev":         {"aliases": ["Stryd Elevation (m)"]},
    "stiffness":          {"aliases": ["Stiffness"]},
    "stiffness_kg":       {"aliases": ["Stiffness/kg"]},
    "ts_local":           {"aliases": ["Local Timestamp"]},             # produced in edit_stryd_csv
    "delta_s":            {"aliases": ["Time Delta"]},                  # produced in edit_stryd_csv
    "dist_delta":         {"aliases": ["Distance Delta"]},              # produced in edit_stryd_csv
    "wt_name":            {"aliases": ["Workout Name"]},                # produced later in pipeline
}

GARMIN_PARSE_SPEC = {
    "date":               {"aliases": ["Date"]},
    "wt_name":            {"aliases": ["Workout Name", "Title"]},
    "avg_hr":             {"aliases": ["Avg HR", "Average HR", "Average Heart Rate", "Avg. HR", "Avg HR (bpm)"]},

}


def make_dt_value(mode="local"):
    return partial(as_aware, tz=get_tzinfo()) if mode == "local" else to_utc


def build_metrics(dt_mode: Literal["local", "utc"] = "local"):
    """ Builds a dictionary based on the METRICS_SPEC registry """
    reg = {"id":str, "wt_name":str, "wt_type":str,
           "dt":make_dt_value(dt_mode),
           "power":fmt_str_decimals, "duration": fmt_hms, "pace":fmt_pace_km,
           "ground":int, "lss":fmt_str_decimals, "cadence":int,
           "vo":fmt_str_decimals, "distance":fmt_distance_km_str, "avg_hr":int}
    return {k: {**spec, "formatter": reg[spec["formatter"]]} for k, spec in METRICS_SPEC.items()}


def align_df_to_metric_keys(
    df: pd.DataFrame,
    metrics: dict,
    keys: set[str] | None = None,
) -> pd.DataFrame:
    """ Align DataFrame columns to canonical metric keys """

    rename_map: dict[str, str] = {}
    cols = set(df.columns)

    for k, spec in metrics.items():
        if keys is not None and k not in keys:
            continue

        # Skip if canonical already present
        if k in cols:
            continue

        # Prefer aliases (typical for parsing Stryd CSVs)
        if "aliases" in spec:
            aliases = spec["aliases"]
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases:
                if alias in cols:
                    rename_map[alias] = k
                    break
        # Fallback to 'key' (typical for report/DB mappings)
        elif "key" in spec:
            src = spec["key"]
            if src in cols and src != k:
                rename_map[src] = k

    if not rename_map:
        return df
    return df.rename(columns=rename_map)


def axis_label(metric: dict) -> str:
    """Return label with unit if available."""
    unit = metric.get("unit")
    return f"{metric['label']} ({unit})" if unit else metric["label"]


