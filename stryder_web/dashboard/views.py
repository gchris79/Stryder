from datetime import timedelta
from io import BytesIO
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.dateparse import parse_date
from stryder_core.plot_core import plot_single_series, X_AXIS_SPEC
from stryder_core.reports import get_single_run_query
from stryder_core.usecases import get_dashboard_summary, get_single_run_summary
from django.conf import settings
from .core_services import get_bootstrap, get_metrics, get_conn
from django.utils import timezone
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt


# Create your views here.
def dashboard_list(request):
    get_bootstrap()
    conn = get_conn()
    tz_str = settings.STRYDER_CORE_CONFIG.get("TIMEZONE")

    default_days = 45

    # 1) optional search by workout name/type
    key = (request.GET.get("key") or "").strip()

    # 2a) dates from request
    start_raw = (request.GET.get("start") or "").strip()
    end_raw = (request.GET.get("end") or "").strip()

    # 2b) if user give dates, parse them
    start_dt = parse_date(start_raw) if start_raw else None
    end_dt = parse_date(end_raw) if end_raw else None

    # 2c) if user didn't give any dates use default last x days
    if not start_dt and not end_dt:
        #today = date.today()
        today = timezone.localdate()
        end_dt = today
        start_dt = today - timedelta(days=default_days - 1)
        # pre-fill the form with these defaults
        start_raw, end_raw = start_dt.isoformat(), end_dt.isoformat()

    # 2d) normalize swapped date range
    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
        start_raw, end_raw = start_dt.isoformat(), end_dt.isoformat()

    # 3) create summary table from core using the inserted dates
    try:
        ctx = get_dashboard_summary(conn, tz_str, end_date=end_dt,
        start_date=start_dt, keyword=key if key else None)
    finally:
        conn.close()

    # 4) Set the paginator and page size
    paginator = Paginator(ctx["runs"], 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 5) Build ctx for use in filtering
    ctx["page_obj"] = page_obj
    ctx["key"] = key              # form keeps the typed keyword
    ctx["start"] = start_raw
    ctx["end"] = end_raw

    return render(request,"dashboard/dashboard_list.html", ctx)


def dashboard_detail(request, run_id):
    get_bootstrap()          # ensures runtime_context is set once
    metrics = get_metrics()  # cached

    # Build y-axis options from canonical metrics
    y_axis_options = []
    for key, meta in metrics.items():
        if meta.get("plottable_single"):
            y_axis_options.append({
                "key": key,  # canonical key, e.g. "power"
                "label": meta["label"],  # what user sees on radio
            })

    # Determine currently selected y-axis from GET (default to first or "power")
    selected_y = request.GET.get("y", "power")
    valid_keys_y = {opt["key"] for opt in y_axis_options}

    selected_x = request.GET.get("x", "elapsed_sec")
    valid_keys_x = set(X_AXIS_SPEC.keys())
    x_axis_options = [
        {"key": k, **meta}
        for k, meta in X_AXIS_SPEC.items()
    ]

    if selected_y not in valid_keys_y:
        # Fallback: choose "power" if available, or the first option
        if "power_sec" in valid_keys_y:
            selected_y = "power_sec"
        else:
            selected_y = next(iter(valid_keys_y))  # first option

    if selected_x not in valid_keys_x:
        # Fallback: choose "power" if available, or the first option
        if "elapsed_sec" in valid_keys_x:
            selected_x = "elapsed_sec"
        else:
            selected_x = next(iter(valid_keys_x))  # first option

    # Build the titles for the graph
    y_label = metrics[selected_y]["label"]
    y_unit = metrics[selected_y]["unit"]

    x_label = X_AXIS_SPEC[selected_x]["label"]
    x_unit = X_AXIS_SPEC[selected_x]["unit"]

    graph_title = f"{y_label} ({y_unit}) over {x_label} {x_unit}"

    conn = get_conn()

    try:
        ctx = get_single_run_summary(conn, run_id, metrics)
    finally:
        conn.close()

    context = {
        "run_id": ctx["run_id"],
        "summary":ctx["summary"],
        "dt": ctx["dt"],
        "wt_name": ctx["wt_name"],
        "y_axis_options": y_axis_options,
        "current_y": selected_y,
        "x_axis_options": x_axis_options,
        "current_x": selected_x,
        "graph_title": graph_title,
    }

    return render(request, "dashboard/dashboard_detail.html", context)


def run_plot(request, run_id):
    get_bootstrap()
    metrics = get_metrics()

    conn = get_conn()
    try:
        df_raw = get_single_run_query(conn, run_id, metrics)
    finally:
        conn.close()

    if df_raw.empty:
        return HttpResponse(status=404)

    selected_y = request.GET.get("y", "power")
    y_label = metrics[selected_y]["label"]

    selected_x = request.GET.get("x", "elapsed_sec")
    x_label = X_AXIS_SPEC[selected_x]["label"]

    fig, ax = plt.subplots()

    plot_single_series(
        df_raw,
        x_col=selected_x,
        y_col=selected_y,
        ax=ax,
        y_label=y_label,
        x_label=x_label
    )

    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)

    return HttpResponse(buf.getvalue(), content_type="image/png")
