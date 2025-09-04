import os
from pathlib import Path
from typing import Literal
import pandas as pd
from datetime import date
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.ticker import FuncFormatter, Locator, MultipleLocator
import matplotlib.dates as mdates
from reports import render_single_run_report
from utils import print_table, prompt_menu, MenuItem, weekly_table_fmt, fmt_hms_to_sec, fmt_sec_to_hms, \
    fmt_pd_sec_to_hms, calc_df_to_pace, fmt_pace


def plot_distance_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Distance (km)", label=label)


def plot_duration_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    df2 = df.copy()
    df2["Hours"] = df2["Duration"].apply(fmt_hms_to_sec)

    fmt_hm = FuncFormatter(lambda y, pos: f"{int(y//3600):02}:{int((y%3600)//60):02}")
    loc_30min = MultipleLocator(1800)  # ticks every 30 minutes

    return plot_weekly_series(
        df2,y_col= "Hours", label=label,
        y_formatter=fmt_hm, y_locator=loc_30min
    )


def plot_power_over_time_batch(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Avg Power", label=label)


def plot_hr_over_time(df: pd.DataFrame, *, y_col: str, label: str, ax=None) -> Axes:
    return plot_weekly_series(df, y_col="Avg HR", label=label)


def what_to_print(
    display: Literal["table", "graph", "both"],
    label: str,
    df: pd.DataFrame,
    report: Literal["single", "batch"],
    x_axis: Literal["duration", "distance"],
    y_axis: Literal["distance","time","power","hr","pace","gt","lss","cad","vo"] | None = None,
    export: bool = False,
    out_dir: str | Path = Path("plots"),
    show: bool = True,
    dpi: int = 300,
) -> Path | None:  # return saved path if you export, else None
    """ The orchestrator that set what will be printed. """

    if display == "table":
        if  report == "single":
            single_run = render_single_run_report(df)
            print_table(single_run)
        elif report == "batch":
            print(f"\n🗓️ {label}")
            print_table(weekly_table_fmt(df))

    elif display == "graph":
        if report == "single":
            plot_func, x_tag, pretty_y, y_tag = graph_menu_single()
            ax = plot_func(df, x_col=x_tag, y_col=y_tag, label=label)
            fig = ax.figure
            if show:
                plt.show(block=False)
            if export:
                save_plot(out_dir, dpi, y_tag)

        elif report == "batch":
            plot_func, pretty_y, y_tag = graph_menu_batch(label, df)
            ax = plot_func(df, y_col=pretty_y, label=label)
            fig = ax.figure
            if show:
                plt.show(block=False)
            if export:
                save_plot(out_dir,dpi,y_tag)
            #plt.close(fig)

    elif display == "both":
        if report == "single":
            plot_func, x_tag, pretty_y, y_tag = graph_menu_single()
            ax = plot_func(df, x_col=x_tag, y_col=y_tag, label=label)
            fig = ax.figure
            if show:
                plt.show(block=False)
            if export:
                save_plot(out_dir, dpi, y_tag)
            print(f"\n🗓️ {label}")
            single_run = render_single_run_report(df)
            print_table(single_run)
        elif report == "batch":
            plot_func, pretty_y, y_tag = graph_menu_batch(label, df)
            ax = plot_func(df, y_col=pretty_y, label=label)
            fig = ax.figure
            if show:
                plt.show(block=False)
            if export:
                save_plot(out_dir,dpi,y_tag)
            print(f"\n🗓️ {label}")
            print_table(weekly_table_fmt(df))
            #plt.close(fig)


def save_plot(path : Path, dpi, y_tag):
    """ Saves a plot """
    os.makedirs(path, exist_ok=True)
    filename = f"{path}/weekly_km_{date.today().isoformat()}_{y_tag}.png"
    plt.savefig(filename, dpi=dpi, bbox_inches="tight")


def plot_single_series(
    df: pd.DataFrame,
    x_col: str = "duration",
    y_col: str = "power",
    label: str = "",
    *,
    rotation: int = 30,
    x_formatter: FuncFormatter | None = None,
    x_locator: Locator | None = None,
    y_formatter: FuncFormatter | None = None,
    y_locator: Locator | None = None,
    ax=None,
):
    # setting the x-axis of the plot
    if x_col == "duration":
        x = (df["dt"] - df["dt"].iloc[0]).dt.total_seconds()
        x_formatter = fmt_pd_sec_to_hms
        x_locator = 600
    elif x_col == "distance":
        x = (df["stryd_distance"] - df["stryd_distance"].min()) / 1000.0
    else:
        raise ValueError(f"Bad x_col={x_col}")

    # setting the y-axis of the plot
    if y_col in ("power", "stiffness", "vertical_oscillation"):
        y = df[y_col].astype(float)

    elif y_col == "pace":
        y = calc_df_to_pace(df, "dt", "stryd_distance")
        y_formatter = fmt_pace

    elif y_col in ("ground_time", "cadence"):
        y = df[y_col].astype(int)

    if ax is None:
        fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.tick_params(axis="x", rotation=rotation)

    if x_formatter:
        ax.xaxis.set_major_formatter(FuncFormatter(x_formatter))
    if x_locator:
        ax.xaxis.set_major_locator(MultipleLocator(x_locator))

    if y_formatter:
        ax.yaxis.set_major_formatter(FuncFormatter(y_formatter))
    if y_locator:
        ax.yaxis.set_major_locator(y_locator)

    ax.set_title(label)
    ax.set_xlabel({
        "duration": "Time (min)", "distance": "Distance (km)",
                  }.get(x_col, x_col)
        )
    ax.set_ylabel({
        "power" : "Power (W/kg)", "pace" : "Pace (min/km)",
        "ground_time" : "Ground Time (ms)", "stiffness" : "Leg Spring Stiffness (kN/m)",
        "cadence" : "Cadence (spm)", "vertical_oscillation" : "Vertical Oscillation (mm)"
                  }.get(y_col, y_col)
        )

    plt.tight_layout()
    return ax


def plot_weekly_series(
    weekly: pd.DataFrame,
    y_col: str = "distance",
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


def graph_menu_single():

    items1 = [
        MenuItem("1", "Time (h:m:s)"),
        MenuItem("2", "Distance (km)"),
    ]

    items2 = [
        MenuItem("1", "Power"),
        MenuItem("2", "Pace"),
        MenuItem("3", "Ground Time"),
        MenuItem("4", "LSS"),
        MenuItem("5", "Cadence"),
        MenuItem("6", "Vertical Oscillation"),
    ]

    choice_x = prompt_menu("Choose X-axis", items1)

    x_tag = "duration" if choice_x == "1" else "distance"
    choice_y = prompt_menu("Choose Y-axis", items2)
    if choice_y in ("1", "power"):
        return plot_single_series, x_tag, "Power (W/kg)", "power"

    elif choice_y in ("2", "pace"):
        return plot_single_series, x_tag, "Pace (min/km)", "pace"

    elif choice_y in ("3", "gt"):
        return plot_single_series, x_tag, "Ground Time (ms)", "ground_time"

    elif choice_y in ("4", "lss"):
        return plot_single_series, x_tag, "Leg Spring Stiffness (kN/m)", "stiffness"

    elif choice_y in ("5", "cad"):
        return plot_single_series, x_tag, "Cadence (spm)", "cadence"

    elif choice_y in ("6", "vo"):
        return plot_single_series, x_tag, "Vertical Oscillation (mm)", "vertical_oscillation"

    elif choice_y == "b":
        return

    elif choice_y == "q":
        exit(0)


def graph_menu_batch(label, weekly):


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
        return plot_power_over_time_batch, "Average Power (W/kg)", "power"

    elif choice1 == "4":
        return plot_hr_over_time, "Average Heart Rate", "hr"

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)


def display_menu(label, df, df_type):
    items1 = [
        MenuItem("1", "Table only"),
        MenuItem("2", "Graph only"),
        MenuItem("3", "Table and Graph"),
    ]

    choice1 = prompt_menu("Display", items1)

    if choice1 in ["1"]:
        what_to_print("table", label, df, df_type, "", "")

    elif choice1 in ["2"]:
        what_to_print("graph", label, df, df_type, " "," ")

    elif choice1 in ["3"]:
        what_to_print("both", label, df, df_type, "", "")

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)