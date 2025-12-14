from datetime import date, timedelta
from django.shortcuts import render
from django.utils.dateparse import parse_date
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_core.usecases import get_dashboard_summary
from .models import Run


# Create your views here.
def dashboard_list(request):
    data = load_json(CONFIG_PATH)
    resolved = bootstrap_context_core(data)
    tz_str = data["TIMEZONE"]
    conn = connect_db(DB_PATH)
    default_days = 45

    # 1) base queryset (join related tables for efficiency)
    qs = Run.objects.select_related("workout", "workout__workout_type").all()

    # 2) optional search by workout name/type
    key = (request.GET.get("key") or "").strip()
    if key:
        qs = qs.filter(workout__workout_name__icontains=key)

    # 3) dates from request
    start_raw = (request.GET.get("start") or "").strip()
    end_raw = (request.GET.get("end") or "").strip()

    # 4a) if user give dates, parse them
    start_dt = parse_date(start_raw) if start_raw else None
    end_dt = parse_date(end_raw) if end_raw else None

    # 4b) if user didn't give any dates use default last x days
    if not start_dt and not end_dt:
        today = date.today()
        end_dt = today
        start_dt = today - timedelta(days=default_days - 1)
        # pre-fill the form with these defaults
        start_raw, end_raw = start_dt.isoformat(), end_dt.isoformat()

    # normalize swapped range
    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
        start_raw, end_raw = start_dt.isoformat(), end_dt.isoformat()

    # 5) apply date filters to ORM queryset
    if start_dt:
        qs = qs.filter(datetime__date__gte=start_dt)
    if end_dt:
        qs = qs.filter(datetime__date__lte=end_dt)

    ctx = get_dashboard_summary(conn, tz_str, end_date=end_dt,
        start_date=start_dt, keyword=key if key else None)

    # 7) overwrite runs in ctx with ORM runs + inject filters
    ctx["runs"] = qs
    ctx["key"] = key              # so the form keeps the typed keyword
    ctx["start"] = start_raw
    ctx["end"] = end_raw

    return render(request,"dashboard/dashboard_list.html", ctx)