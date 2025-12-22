from datetime import timedelta, date
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.dateparse import parse_date

from stryder_cli.cli_main import bootstrap_defaults_interactive
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.metrics import build_metrics
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_core.usecases import get_dashboard_summary, get_single_run_summary


# Create your views here.
def dashboard_list(request):
    data = load_json(CONFIG_PATH)
    resolved = bootstrap_context_core(data)
    tz_str = data["TIMEZONE"]
    conn = connect_db(DB_PATH)
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
        today = date.today()
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
    conn = connect_db(DB_PATH)
    paths = bootstrap_defaults_interactive()            # Get saved tz, paths, etc.
    metrics = build_metrics("local")

    try:
        ctx = get_single_run_summary(conn, run_id, metrics)
    finally:
        conn.close()

    return render(request, "dashboard/dashboard_detail.html", ctx)
