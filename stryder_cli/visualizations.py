from typing import Literal
import pandas as pd
from pathlib import Path
import matplotlib, matplotlib.pyplot as plt
from stryder_cli.cli_utils import MenuItem, prompt_menu, print_table
from stryder_core.metrics import axis_label
from stryder_core.plot_core import plot_distance_over_time, plot_duration_over_time, plot_power_over_time_batch, \
    plot_hr_over_time, plot_single_series, save_plot
from stryder_core.table_formatters import weekly_table_fmt


def resolve_plots_dir() -> Path:
    """Return the absolute path to project-root/plots."""
    return Path(__file__).resolve().parents[1] / "plots"


def save_cli_wrapper(dpi, name, fig=None):
    plot_dir = resolve_plots_dir()
    path = save_plot(plot_dir, dpi, name, fig=fig)
    print(f"[plot] Saved: {path}")
    return path


def finish_plot(fig=None, title="plot"):
    """ Show the figure if the backend is GUI; otherwise save to disk.
       If showing fails for any reason, fall back to saving. """

    # Small helper to avoid duplication of code
    def _save_fallback(reason: str):
        out = resolve_plots_dir() / f"{title}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[plot] {reason} → saved: {out}")
        return out

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
        return _save_fallback("Non GUI backend")

    try:
        plt.show()  # blocking; window stays until closed
        return None
    except Exception as e:
        return _save_fallback(f"show() failed ({type(e).__name__}: {e})")


def what_to_print(
    display: Literal["table", "graph", "both"],
    label: str,
    df: pd.DataFrame,
    report: Literal["single", "batch"],
    export: bool = False,   # Save or not
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
                save_cli_wrapper(dpi,y_tag, fig=fig)

        elif report == "batch":
            if (result := graph_menu_batch(metrics)) is None:      # Guard for if user gets back before choosing an option
                return                                      # Return to previous menu safely
            plot_func, pretty_y, y_tag = result             # Safe unpacking

            ax = plot_func(df, y_col=y_tag, label=pretty_y)
            fig = ax.figure
            if show:
                finish_plot(fig, title="weekly_summary")
            if export:
                save_cli_wrapper(dpi,y_tag, fig=fig)


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
                save_cli_wrapper(dpi,y_tag, fig=fig)

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
                save_cli_wrapper(dpi,y_tag, fig=fig)


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