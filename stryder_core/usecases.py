from datetime import date, timedelta
from stryder_cli.cli_queries import get_workouts_by_date
from stryder_core import runtime_context
from stryder_core.config import DB_PATH
from stryder_core.date_utilities import resolve_tz
from stryder_core.db_schema import connect_db
from stryder_core.metrics import build_metrics


def get_rolling_week_for_web(db_path=DB_PATH,
    timezone_str="Europe/Athens", days=7):

    tz_info = resolve_tz(timezone_str)
    runtime_context.set_context(tz_str=timezone_str, tzinfo=tz_info)

    conn = connect_db(db_path)

    metrics = build_metrics("local")

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    rows = get_workouts_by_date(start_date, end_date, conn, metrics, mode="for_views")

    runs = []
    for row in rows:
        run_date, wt_name, distance_km, duration_str, power_avg, avg_hr, wt_type = row
        runs.append({
            "dt": run_date,
            "wt_name": wt_name,
            "distance": distance_km,
            "duration": duration_str,
            "power_avg": power_avg,
            "HR": avg_hr,
            "wt_type": wt_type,
        })
    return runs