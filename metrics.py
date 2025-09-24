from functools import partial
from typing import TypedDict, Literal, Callable, Any
import pandas as pd
from runtime_context import get_tzinfo
from date_utilities import to_utc, as_aware
from utils import fmt_pace, fmt_distance, fmt_sec_to_hms


class MetricInfo(TypedDict, total=False):
    key: str
    label: str
    unit: str
    formatter: str | Callable[[Any], Any]


METRICS_SPEC : dict[str ,MetricInfo] = {
    "id":        {"key": "run_id",              "label": "Run ID",                          "formatter": "id"},
    "wt_name":   {"key": "wt_name",             "label": "Workout Name",                    "formatter": "wt_name"},
    "wt_type":   {"key": "wt_type",             "label": "Workout Type",                    "formatter": "wt_type"},
    "dt":        {"key": "datetime",            "label": "Datetime",                        "formatter" : "dt"},
    "power_sec": {"key": "power",               "label": "Power",         "unit": "W/kg",   "formatter": "power"},
    "power_avg": {"key": "avg_power",           "label": "Avg Power",     "unit": "W/kg",   "formatter": "power"},
    "duration":  {"key": "duration_sec",        "label": "Duration",      "unit": "h:m",    "formatter": "duration"},
    "pace":      {"key": "pace",                "label": "Pace",          "unit": "min/km", "formatter": "pace"},
    "ground":    {"key": "ground_time",         "label": "Ground Time",   "unit": "ms",     "formatter": "ground"},
    "lss":       {"key": "stiffness",           "label": "LSS",           "unit": "kN/m",   "formatter": "lss"},
    "cadence":   {"key": "cadence",             "label": "Cadence",       "unit": "spm",    "formatter": "cadence"},
    "vo":        {"key": "vertical_oscillation","label": "V.Oscillation", "unit": "mm",     "formatter": "vo"},
    "distance":  {"key": "distance_m",          "label": "Distance",      "unit": "m",      "formatter": "distance"},
    "HR":        {"key": "avg_hr",              "label": "Avg HR",        "unit": "bpm",    "formatter": "HR"}

}


def make_dt_value(mode="local"):
    return partial(as_aware, tz=get_tzinfo()) if mode == "local" else to_utc


def build_metrics(dt_mode: Literal["local", "utc"] = "local"):
    reg = {"id":str, "wt_name":str, "wt_type":str,
           "dt":make_dt_value(dt_mode),
           "power":float, "duration": fmt_sec_to_hms, "pace":fmt_pace,
           "ground":int, "lss":float, "cadence":int,
           "vo":float, "distance":fmt_distance, "HR":int}
    return {k: {**spec, "formatter": reg[spec["formatter"]]} for k, spec in METRICS_SPEC.items()}


def align_df_to_metric_keys(
    df: pd.DataFrame,
    metrics: dict,
    keys: set[str] | None = None,   # ← align only these metrics if provided
) -> pd.DataFrame:
    rename_map = {}
    for k, spec in metrics.items():
        if keys is not None and k not in keys:
            continue
        src = spec.get("key", k)
        if src in df.columns and src != k:
            rename_map[src] = k
    return df.rename(columns=rename_map)


def axis_label(metric: dict) -> str:
    """Return label with unit if available."""
    unit = metric.get("unit")
    return f"{metric['label']} ({unit})" if unit else metric["label"]


