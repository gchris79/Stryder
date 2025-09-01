import os
from pathlib import Path
from typing import Literal

import pandas as pd
from datetime import date
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, Locator, MultipleLocator
import matplotlib.dates as mdates
from utils import print_table, prompt_menu, MenuItem, weekly_table_fmt, hms_to_seconds


def plot_distance_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Distance (km)", label=label)


def plot_duration_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    df2 = df.copy()
    df2["Hours"] = df2["Duration"].apply(hms_to_seconds)

    fmt_hm = FuncFormatter(lambda y, pos: f"{int(y//3600):02}:{int((y%3600)//60):02}")
    loc_30min = MultipleLocator(1800)  # ticks every 30 minutes

    return plot_weekly_series(
        df2, y_col="Hours", label=label,
        y_formatter=fmt_hm, y_locator=loc_30min
    )


def plot_power_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Avg Power", label=label)


def plot_hr_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Avg HR", label=label)


def what_to_print(
    display: Literal["table", "graph", "both"],
    label: str,
    weekly: pd.DataFrame,
    y_axis: Literal["distance","time","power","hr"] | None = None,
    export: bool = False,
    out_dir: str | Path = Path("plots"),
    show: bool = True,
    dpi: int = 300,
) -> Path | None:  # return saved path if you export, else None
    """ The orchestrator that set what will be printed. """

    if display == "table":
        print(f"\n🗓️ {label}")
        print_table(weekly_table_fmt(weekly))

    elif display == "graph":
        plot_func, pretty_y, y_tag = graph_menu(label, weekly)
        ax = plot_func(weekly, y_col=pretty_y, label=label)
        fig = ax.figure
        if show is True:
            plt.show(block=False)
        if export:
            save_plot(out_dir,dpi,y_tag)
        #plt.close(fig)

    elif display == "both":
        plot_func, pretty_y, y_tag = graph_menu(label, weekly)
        ax = plot_func(weekly, y_col=pretty_y, label=label)
        fig = ax.figure
        if show is True:
            plt.show(block=False)
        if export:
            save_plot(out_dir,dpi,y_tag)
        print(f"\n🗓️ {label}")
        print_table(weekly_table_fmt(weekly))
        #plt.close(fig)


def save_plot(path : Path, dpi, y_tag):
    """ Saves a plot """
    os.makedirs(path, exist_ok=True)
    filename = f"{path}/weekly_km_{date.today().isoformat()}_{y_tag}.png"
    plt.savefig(filename, dpi=dpi, bbox_inches="tight")


def plot_weekly_series(
    weekly: pd.DataFrame,
    y_col: str = "Distance (km)",
    label: str = "",
    *,
    center: bool = True,
    width_days: int = 3,
    tick_mode: str = "exact",   # "exact" or "monday"
    date_fmt: str = "%b %d",
    rotation: int = 30,
    y_formatter: FuncFormatter | None = None,
    y_locator: Locator | None = None,
    ax=None,
):


    x = pd.to_datetime(weekly["week_start"], errors="coerce").dt.tz_localize(None).dt.normalize()
    y = weekly[y_col].astype(float)

    if ax is None:
        fig, ax = plt.subplots()

    ax.bar(x, y, width=width_days, align=("center" if center else "edge"))

    if tick_mode == "exact":
        ax.set_xticks(x)
    elif tick_mode == "monday":
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    else:
        raise ValueError("tick_mode must be 'exact' or 'monday'")

    ax.xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
    ax.tick_params(axis="x", rotation=rotation)

    if y_formatter:
        ax.yaxis.set_major_formatter(y_formatter)
    if y_locator:
        ax.yaxis.set_major_locator(y_locator)

    ax.set_title(label)
    ax.set_ylabel({
        "Distance (km)": "Distance (km)",
        "Duration": "Duration",
        "avg_power": "Average Power (W/kg)",
        "avg_hr": "Average HR (bpm)",
    }.get(y_col, y_col))

    plt.tight_layout()
    return ax


def graph_menu(label, weekly):


    items1 = [
        MenuItem("1", "Weekly Distance"),
        MenuItem("2", "Weekly Duration"),
        MenuItem("3", "Weekly Average Power"),
        MenuItem("4", "Weekly Average Heart Rate"),
    ]

    choice1 = prompt_menu("Graphs", items1)

    if choice1 == "1":
        return plot_distance_over_time, "Distance (km)", "distance"

    elif choice1 == "2":
        return plot_duration_over_time, "Duration", "duration"

    elif choice1 == "3":
        return plot_power_over_time, "Average Power (W/kg)", "power"

    elif choice1 == "4":
        return plot_hr_over_time, "Average Heart Rate", "HR"

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)


def display_menu(label, weekly):
    items1 = [
        MenuItem("1", "Table only"),
        MenuItem("2", "Graph only"),
        MenuItem("3", "Table and Graph"),
    ]

    choice1 = prompt_menu("Display", items1)

    if choice1 in ["1"]:
        what_to_print("table", label, weekly)

    elif choice1 in ["2"]:
        what_to_print("graph", label, weekly)

    elif choice1 in ["3"]:
        what_to_print("both", label, weekly)

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)