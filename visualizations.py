import os
import pandas as pd
from datetime import date
from matplotlib import pyplot as plt
from matplotlib.ticker import FuncFormatter, Locator, MultipleLocator
import matplotlib.dates as mdates
from utils import print_table, prompt_menu, MenuItem, weekly_table_fmt, hms_to_seconds


def plot_distance_over_time(weekly, label):
    return plot_weekly_series(weekly, y_col="Distance (km)", label=label)


def plot_duration_over_time(weekly, label):
    df = weekly.copy()
    df["Hours"] = df["Duration"].apply(hms_to_seconds)

    fmt_hm = FuncFormatter(lambda y, pos: f"{int(y//3600):02}:{int((y%3600)//60):02}")
    loc_30min = MultipleLocator(1800)  # ticks every 30 minutes

    return plot_weekly_series(
        df, y_col="Hours", label=label,
        y_formatter=fmt_hm, y_locator=loc_30min
    )


def plot_power_over_time(weekly, label):
    return plot_weekly_series(weekly, y_col="Avg Power", label=label)


def plot_hr_over_time(weekly, label):
    return plot_weekly_series(weekly, y_col="Avg HR", label=label)


def show_table_and_plot(df, plot_func,*args,**kwargs):
    """
      Print a DataFrame as table and show a plot at the same time.

      Parameters
      ----------
      df : pd.DataFrame
          The summary table to print.
      plot_func : callable
          A plotting function that takes the DataFrame as first argument.
      *args, **kwargs
          Extra arguments passed to the plotting function.
      """
    print_table(weekly_table_fmt(df))
    plt.close("all")
    plot_func(df, *args, **kwargs)
    plt.show(block=False)


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


def save_plot():
    os.makedirs("plots", exist_ok=True)
    filename = f"plots/weekly_km_{date.today().isoformat()}.png"
    plt.savefig(filename, dpi=300, bbox_inches="tight")


def graph_menu(weekly):


    items1 = [
        MenuItem("1", "Weekly Distance"),
        MenuItem("2", "Weekly Duration"),
        MenuItem("3", "Weekly Average Heart Rate"),
        MenuItem("4", "Weekly Average Power"),
    ]

    choice1 = prompt_menu("Graphs", items1)

    # 1) Last N weeks
    if choice1 == "1":
        show_table_and_plot(weekly, plot_distance_over_time, "Distance (km)")

    elif choice1 == "2":
        show_table_and_plot(weekly, plot_duration_over_time, "Duration")

    elif choice1 == "3":
        show_table_and_plot(weekly, plot_hr_over_time, "Average Heart Rate")

    elif choice1 == "4":
        show_table_and_plot(weekly, plot_power_over_time, "Average Power (W/kg)")

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

    if choice1 == "1":
        print(f"\n🗓️ {label}")
        print_table(weekly_table_fmt(weekly))


    elif choice1 == "2":
        graph_menu(weekly)



    elif choice1 == "3":
        print(f"\n🗓️ {label}")
        graph_menu(weekly)





    elif choice1 == "b":
        return



    elif choice1 == "q":
        exit(0)