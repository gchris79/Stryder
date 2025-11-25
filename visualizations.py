import re
from collections.abc import Callable
from datetime import datetime
from typing import Literal
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib, matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, Locator, MultipleLocator
import matplotlib.dates as mdates
from stryder_core.metrics import axis_label
from utils import print_table, prompt_menu, MenuItem, calc_df_to_pace
from stryder_core.formatting import weekly_table_fmt, fmt_hm, fmt_pace_no_unit


def finish_plot(fig=None, title="plot"):
    """ Show the figure if the backend is GUI; otherwise save to disk.
       If showing fails for any reason, fall back to saving. """
    if fig is None:
        fig = plt.gcf()

    backend = matplotlib.get_backend()
    b = backend.lower()
    # Treat truly non-GUI backends (and inline/module backends) as save-only
    non_gui = (
        b in {"agg", "pdf", "ps", "svg", "cairo", "template", "pgf"}
        or "inline" in b
        or b.startswith("module://")
    )
    print(f"[plot] backend={backend} non_gui={non_gui} interactive={plt.isinteractive()}")

    if non_gui:
        out = Path("plots") / f"{title}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[plot] Non-GUI backend → saved: {out}")
        return out

    try:
        plt.show()  # blocking; window stays until closed
        return None
    except Exception as e:
        out = Path("plots") / f"{title}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[plot] show() failed ({type(e).__name__}: {e}) → saved: {out}")
        return out


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


def what_to_print(
    display: Literal["table", "graph", "both"],
    label: str,
    df: pd.DataFrame,
    report: Literal["single", "batch"],
    export: bool = False,
    out_dir: str | Path = Path("plots"),
    show: bool = True,
    dpi: int = 300,
    metrics: dict = None
) -> Path | None:  # return saved path if you export, else None
    """ The orchestrator that sets what will be printed. """

    from stryder_core.reports import render_single_run_report

    if display == "table":
        if  report == "single":
            single_run = render_single_run_report(df)
            print_table(single_run)
        elif report == "batch":
            print(f"\n🗓️ {label}")
            print_table(weekly_table_fmt(df, metrics))

    elif display == "graph":
        if report == "single":
            if (result := graph_menu_single(metrics,df)) is None:     # Guard for if user gets back before choosing an option
                return                                      # Return to previous menu safely
            plot_func, x_tag, pretty_y, y_tag = result      # Safe unpacking

            ax = plot_func(df, x_col=x_tag, y_col=y_tag, label=pretty_y)
            fig = ax.figure
            if show:
                finish_plot(fig, title="single_run_report")
            if export:
                save_plot(out_dir,dpi,y_tag, fig=fig)

        elif report == "batch":
            if (result := graph_menu_batch(metrics)) is None:      # Guard for if user gets back before choosing an option
                return                                      # Return to previous menu safely
            plot_func, pretty_y, y_tag = result             # Safe unpacking

            ax = plot_func(df, y_col=y_tag, label=pretty_y)
            fig = ax.figure
            if show:
                finish_plot(fig, title="weekly_summary")
            if export:
                save_plot(out_dir,dpi,y_tag, fig=fig)


    elif display == "both":
        if report == "single":
            if (result := graph_menu_single(metrics, df)) is None:     # Guard for if user gets back before choosing an option
                return                                      # Return to previous menu safely
            plot_func, x_tag, pretty_y, y_tag = result      # Safe unpacking
            print(f"\n🗓️ {label}")                                          # print table
            single_run = render_single_run_report(df)
            print_table(single_run)
            ax = plot_func(df, x_col=x_tag, y_col=y_tag, label=pretty_y)       # print graph
            fig = ax.figure
            if show:
                finish_plot(fig, title="single_run_report")
            if export:
                save_plot(out_dir,dpi,y_tag, fig=fig)

        elif report == "batch":
            if (result := graph_menu_batch(metrics)) is None:      # Guard for if user gets back before choosing an option
                return                                      # Return to previous menu safely
            plot_func, pretty_y, y_tag = result
            print(f"\n🗓️ {label}")                                          # print table
            print_table(weekly_table_fmt(df, metrics))
            ax = plot_func(df, y_col=y_tag, label=pretty_y)                 # print graph
            fig = ax.figure
            if show:
                finish_plot(fig, title="weekly_summary")
            if export:
                save_plot(out_dir,dpi,y_tag, fig=fig)


def save_plot(out_dir, dpi, name, fig=None):
    """Save current (or given) fig with a timestamp to avoid overwrites."""
    if out_dir is None:                         # Guard if out_dir become None, "", "   ", defaults to /plots
        s = ""
    else:
        s = str(out_dir).strip()
    if not s:  # covers "", "   ", None
        out_dir = "plots"
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    # very light 'slug': keep letters, numbers, dot, dash, underscore
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_") or "plot"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{safe}_{ts}.png"

    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    print(f"[plot] Saved: {path}")
    return path


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
    ax.tick_params(axis="x", rotation=30 )if x_col == "elapsed_sec" else ax.tick_params(axis="x", rotation=rotation)    # tilt x_axis only if its time, not in distance
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


def graph_menu_single(metrics: dict, df: pd.DataFrame):
    """
    Return: plot_func, x_tag, pretty_y, y_tag
    Assumes df columns are already aligned to metrics keys (aligner strategy).
    """

    # --- X axis ---
    items1 = [MenuItem("1", "Time (h:m:s)"), MenuItem("2", "Distance (km)")]
    cx = prompt_menu("Choose X-axis", items1, allow_back=False, allow_quit=False)
    if cx == "1":
        x_tag = "elapsed_sec"
    elif cx == "2":
        x_tag = "distance_km"
    else:
        return None  # safety

    # --- Build Y options ---
    # Order you want to show in menu:
    candidate_order = ["power_sec", "pace", "ground", "lss", "cadence", "vo"]

    # 'pace' is derived, others must be actual columns in the aligned df
    y_keys = []
    for k in candidate_order:
        if k == "pace":
            if "dt" in df.columns and "distance_m" in df.columns:
                y_keys.append(k)
        else:
            if k in df.columns:          # because DF was aligned to metrics keys
                y_keys.append(k)

    if not y_keys:
        print("⚠️ No plot-able metrics found.")
        return None

    items2 = [MenuItem(str(i+1), axis_label(metrics[k])) for i, k in enumerate(y_keys)]
    cy = prompt_menu("Choose Y-axis", items2, allow_back=True, allow_quit=True)
    if cy in (None, "b", "q"):
        return None

    # Map user's numeric choice (1-based) to the metric key
    try:
        mkey = y_keys[int(cy) - 1]
    except Exception:
        print("⚠️ Invalid choice.")
        return None

    pretty_y = axis_label(metrics[mkey])
    y_tag = mkey                      # DF already has this column (except 'pace', handled in plotter)

    return plot_single_series, x_tag, pretty_y, y_tag


def graph_menu_batch(metrics):
    """ The graph menu """
    items1 = [
        MenuItem("1", "Weekly Distance"),
        MenuItem("2", "Weekly Duration"),
        MenuItem("3", "Weekly Average Power"),
        MenuItem("4", "Weekly Average Heart Rate"),
    ]

    choice1 = prompt_menu("Graphs", items1)

    if choice1 == "1":
        return plot_distance_over_time, axis_label(metrics["distance_km"]), metrics["distance_km"]["key"]

    elif choice1 == "2":
        return plot_duration_over_time, axis_label(metrics["duration"]), metrics["duration"]["key"]

    elif choice1 == "3":
        return plot_power_over_time_batch, axis_label(metrics["power_avg"]), metrics["power_avg"]["key"]

    elif choice1 == "4":
        return plot_hr_over_time, axis_label(metrics["HR"]), metrics["HR"]["key"]

    elif choice1 == "b":
        return None

    elif choice1 == "q":
        exit(0)


def display_menu(label, df_raw, df_type, metrics):
    """ The display menu"""
    items1 = [
        MenuItem("1", "Table only"),
        MenuItem("2", "Graph only"),
        MenuItem("3", "Table and Graph"),
    ]

    choice1 = prompt_menu("Display", items1)

    if choice1 in ["1"]:
        what_to_print("table", label, df_raw, df_type, metrics=metrics)

    elif choice1 in ["2"]:
        what_to_print("graph", label, df_raw, df_type, metrics=metrics)

    elif choice1 in ["3"]:
        what_to_print("both", label, df_raw, df_type, metrics=metrics)

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)