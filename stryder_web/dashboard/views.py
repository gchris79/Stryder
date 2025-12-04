from django.shortcuts import render
from stryder_core.bootstrap import bootstrap_context_core
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db
from stryder_core.path_memory import load_json, CONFIG_PATH
from stryder_core.usecases import get_dashboard_summary


# Create your views here.
def dashboard_list(request):
    data = load_json(CONFIG_PATH)
    resolved = bootstrap_context_core(data)
    tz_str = data["TIMEZONE"]
    conn = connect_db(DB_PATH)
    ctx = get_dashboard_summary(conn, tz_str, days=30)

    return render(
        request,
        "dashboard/dashboard_list.html",
        ctx,
    )