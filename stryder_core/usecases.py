from datetime import date, timedelta
from stryder_core import runtime_context
from stryder_core.config import DB_PATH
from stryder_core.date_utilities import dt_to_string
from stryder_core.db_schema import connect_db
from stryder_core.metrics import build_metrics
from stryder_core.queries import fetch_page, views_query


def format_row_for_ui(row_dict, metrics) -> dict:
    """ Format dict row for UI printing """
    # Convert raw DB value -> datetime object using the same formatter as CLI
    dt_obj = metrics["dt"]["formatter"](row_dict["datetime"])

    # Get tzinfo from runtime_context (assuming you've already set it somewhere)
    tzinfo = runtime_context.get_tzinfo()

    return {
        "dt": dt_to_string(dt_obj, "ymd", tz=tzinfo),
        "distance": metrics["distance"]["formatter"](row_dict["distance_m"]),
        "duration": metrics["duration"]["formatter"](row_dict["duration_sec"]),
        "avg_power": metrics["power_avg"]["formatter"](row_dict["avg_power"]),
        "avg_hr": row_dict["avg_hr"],
        "wt_name": row_dict["wt_name"],
        "wt_type": row_dict["wt_type"],
    }


def get_last_week_for_ui(db_path=DB_PATH, days=30) -> list:
    """ Get last week (set up by days) runs from db and return list of runs """
    conn = connect_db(db_path)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    query = views_query()
    query += " WHERE r.datetime BETWEEN ? AND ?"
    base_params = (start_date, end_date)

    rows, columns, _ = fetch_page(conn, query, base_params, page_size=0)

    metrics = build_metrics("local")


    runs = []
    for row in rows:
        row_dict = dict(zip(columns, row))          # turn tuple → dict
        runs.append(format_row_for_ui(row_dict, metrics))
    return runs