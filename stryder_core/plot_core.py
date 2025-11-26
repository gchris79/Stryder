import re
from datetime import datetime
from pathlib import Path
from typing import Callable
import numpy as np
import pandas as pd
from matplotlib import dates as mdates, pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, MultipleLocator, Locator
from stryder_core.formatting import fmt_hm, fmt_pace_no_unit
from stryder_core.utils import calc_df_to_pace


def plot_distance_over_time(df: pd.DataFrame, *, y_col: str, label: str) -> Axes:
    """ Wrapper for plotting weekly distance over time """
    return plot_weekly_series(df, y_col=y_col, label=label)


def plot_duration_over_time(df: pd.DataFrame, *, y_col: str, label: str) -> Axes:
    """ Wrapper for plotting weekly duration over time """
    fmt_hour_min = FuncFormatter(lambda y, pos: fmt_hm(y))
    loc_30min = MultipleLocator(1800)  # ticks every 30 minutes

    return plot_weekly_series(
        df, y_col=y_col, label=label,
        y_formatter=fmt_hour_min, y_locator=loc_30min
    )

def plot_power_over_time_batch(df: pd.DataFrame, *, y_col: str, label: str) -> Axes:
    """ Wrapper for plotting weekly power over time """
    return plot_weekly_series(df, y_col=y_col, label=label)


def plot_hr_over_time(df: pd.DataFrame, *, y_col: str, label: str) -> Axes:
    """ Wrapper for plotting weekly HR over time """
    return plot_weekly_series(df, y_col=y_col, label=label)


def plot_single_series(
    df: pd.DataFrame,
    x_col: str = "elapsed_sec",           # 'elapsed_sec', 'distance_km', or 'dt'
    y_col: str = "power",
    label: str = "",
    *,
    rotation: int = 0,
    x_formatter: FuncFormatter | Callable | None = None,
    x_locator: int | float | Locator | None = None,
    y_formatter: FuncFormatter | Callable | None = None,
    y_locator: Locator | None = None,
    ax=None,
):
    """ Graph plotter for the single run report """
    # ---- Backward-compatibility aliases ----
    x_alias = {"duration": "elapsed_sec", "distance": "distance_km", "distance_m": "distance_km"}
    x_col = x_alias.get(x_col, x_col)


    # ---- Prepare X data + default formatters/locators ----
    if x_col == "elapsed_sec":
        # compute once if absent
        if "elapsed_sec" not in df.columns:
            df = df.copy()
            df["elapsed_sec"] = (df["dt"] - df["dt"].iloc[0]).dt.total_seconds()
        x = pd.to_numeric(df["elapsed_sec"], errors="coerce")
        if x_formatter is None:
            x_formatter = FuncFormatter(fmt_hm)
        if x_locator is None:
            span = float(x.max()) - float(x.min())
            x_locator = 900 if span >= 3600 else 300  # 15-min ticks for runs ≥ 1h
    elif x_col == "distance_km":
        if "distance_km" in df.columns:
            x = pd.to_numeric(df["distance_km"], errors="coerce")
        else:
            # derive from meters
            x = (pd.to_numeric(df["distance_m"], errors="coerce") - float(df["distance_m"].min())) / 1000.0
        if x_locator is None:
            x_locator = 1.0  # every 1 km
    elif x_col == "dt":
        x = df["dt"]
        if x_formatter is None:
            x_formatter = mdates.DateFormatter("%H:%M:%S")
        if x_locator is None:
            x_locator = mdates.AutoDateLocator()
    else:
        raise ValueError(f"Unsupported x_col={x_col!r}. Use 'elapsed_sec', 'distance_km', or 'dt'.")

    # ---- Prepare Y data + optional default pace formatter ----
    if y_col in df.columns:
        y = pd.to_numeric(df[y_col], errors="coerce")
    elif y_col == "pace":
        # expects per-sample pace (sec/km) computed from dt & distance_m
        y = calc_df_to_pace(df, "dt", "distance_m")
        if y_formatter is None:
            y_formatter = FuncFormatter(fmt_pace_no_unit)
    else:
        raise ValueError(f"y_col '{y_col}' not found in DataFrame and no special handler provided.")

    # ---- Make axes ----
    if ax is None:
        fig, ax = plt.subplots()

    # ---- Plot ----
    mask = np.isfinite(x) & np.isfinite(y)
    ax.plot(x[mask], y[mask], label=(label or None))
    ax.tick_params(axis="x", rotation=30 )if x_col == "elapsed_sec" else ax.tick_params(axis="x", rotation=rotation)    # tilt x_axis only if it's time, not in distance
    ax.grid(True, alpha=0.3)

    # ---- Apply formatters ----
    if x_formatter is not None:
        if not isinstance(x_formatter, FuncFormatter):
            x_formatter = FuncFormatter(x_formatter)  # wrap plain function
        ax.xaxis.set_major_formatter(x_formatter)

    if x_locator is not None:
        if isinstance(x_locator, (int, float)):
            ax.xaxis.set_major_locator(MultipleLocator(x_locator))
        else:
            ax.xaxis.set_major_locator(x_locator)

    if y_formatter is not None:
        if not isinstance(y_formatter, FuncFormatter):
            y_formatter = FuncFormatter(y_formatter)
        ax.yaxis.set_major_formatter(y_formatter)

    if y_locator is not None:
        ax.yaxis.set_major_locator(y_locator)

    # ---- Labels ----
    x_labels = {
        "elapsed_sec": "Duration (h:m:s)",
        "distance_km": "Distance (km)",
        "dt": "Time",
    }
    ax.set_xlabel(x_labels.get(x_col, x_col))
    ax.set_title(label or "")
    ax.set_ylabel(label or y_col)   # use the pretty label

    if label:
        ax.legend()

    plt.tight_layout()
    return ax


def plot_weekly_series(
    weekly: pd.DataFrame,
    *,
    y_col: str,
    label: str,
    center: bool = True,
    width_days: int = 3,
    date_fmt: str = "%b %d",
    rotation: int = 30,
    y_formatter: FuncFormatter | None = None,
    y_locator: Locator | None = None,
    ax=None,
):
    """ Graph plotter for the weekly run report """
    if y_col not in weekly.columns:
        raise ValueError(f"y_col '{y_col}' not in DataFrame columns: {list(weekly.columns)}")

    x = pd.to_datetime(weekly["week_start"], errors="coerce").dt.tz_localize(None).dt.normalize()
    y = weekly[y_col].astype(float)

    if ax is None:
        fig, ax = plt.subplots()

    ax.bar(x, y, width=width_days, align=("center" if center else "edge"))

    ax.set_xticks(x)

    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
    ax.tick_params(axis="x", rotation=rotation)
    ax.grid(True, alpha=0.3)

    if y_formatter:
        ax.yaxis.set_major_formatter(y_formatter)
    if y_locator:
        ax.yaxis.set_major_locator(y_locator)


    ax.set_title(label)
    ax.set_ylabel(label)

    plt.tight_layout()
    return ax


def save_plot(out_dir, dpi, name, fig=None):
    """
    Pure core: Save fig to out_dir, slugifying name and adding a timestamp.
    out_dir must be a valid directory path (absolute or relative).
    """

    out_dir = Path(out_dir)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # very light 'slug': keep letters, numbers, dot, dash, underscore
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_") or "plot"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{safe}_{ts}.png"

    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
