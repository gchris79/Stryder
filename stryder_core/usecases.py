from datetime import date, timedelta
from stryder_core.metrics import build_metrics
from stryder_core.queries import fetch_page, views_query
from stryder_core.reports import custom_dates_report
from stryder_core.table_formatters import format_row_for_ui, format_summary_for_ui


def get_last_days_for_ui(conn, days) -> tuple:
    """ Get last days runs from db and return a tuple of runs """

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
    return runs, start_date, end_date


def get_dashboard_summary(conn, tz_name: str, days) -> dict:
    """ Create a list of runs for the last x days and
        a summary for those runs in dashboard """
    runs, start_date, end_date = get_last_days_for_ui(conn, days=days)
    label, df_summary = custom_dates_report(
        conn,
        tz_name,
        mode="rolling",   # ignored for custom range, but fine
        end_date=end_date,
        start_date=start_date,
    )
    if df_summary.empty:
        summary = None
    else:
        row = df_summary.iloc[0]
        summary = {
            "label": label,
            "runs": int(row["runs"]),
            "distance_km": float(row["distance_km"]),
            "duration_sec": int(row["duration_sec"]),
            "avg_power": float(row["avg_power"]) if row["avg_power"] is not None else None,
            "avg_hr": float(row["avg_hr"]) if row["avg_hr"] is not None else None,
        }
    formated_summary = format_summary_for_ui(summary)
    return {
        "runs": runs,
        "summary": formated_summary,
    }

