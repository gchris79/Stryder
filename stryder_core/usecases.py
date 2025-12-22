from datetime import date, timedelta
from stryder_core.metrics import build_metrics
from stryder_core.queries import fetch_page, views_query
from stryder_core.reports import custom_dates_report, get_single_run_query, render_single_run_report
from stryder_core.table_formatters import format_row_for_ui, format_runs_summary_for_ui


def get_x_days_for_ui(conn, days: int | None = None,
                      end_date: date | None = None,
                      start_date: date | None = None,
                      keyword: str | None = None,
                      ) -> tuple:
    """Get runs and dates for either:
       - last `days`, or
       - explicit [start_date, end_date] range.
    Returns (runs_for_ui, start_date, end_date).
    """
    # days or dates should be inserted else error
    if days is not None:
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)

    if start_date is None or end_date is None:
        raise ValueError("get_last_days_for_ui requires either days or start/end dates")

    # create the query check for dates and the keyword
    query = views_query()
    conditions = ["r.datetime BETWEEN ? AND ?"]
    params: list = [start_date, end_date]

    if keyword:
        # Search by workout name, also by type name
        conditions.append("(w.workout_name LIKE ? OR wt.name LIKE ?)")
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    query += " WHERE " + " AND ".join(conditions)

    rows, columns, _ = fetch_page(conn, query, tuple(params), page_size=0)

    metrics = build_metrics("local")

    runs = []
    for row in rows:
        row_dict = dict(zip(columns, row))          # turn tuple → dict
        runs.append(format_row_for_ui(row_dict, metrics))
    return runs, end_date, start_date


def get_dashboard_summary(conn, tz_name,
                          days: int | None =    None,
                          end_date: date | None = None,
                          start_date: date | None = None,
                          keyword: str | None = None,) -> dict:
    """Build ctx with 'runs' (formatted for UI) and 'summary' for dashboard."""

    # if days is given, ignore start/end; otherwise use explicit range
    runs, end_date, start_date = get_x_days_for_ui(
        conn,
        days=days,
        end_date=end_date,
        start_date=start_date,
        keyword=keyword,
    )

    label, df_summary = custom_dates_report(
        conn,
        tz_name,
        mode="rolling",   # ignored for custom range, fine
        end_date=end_date,
        start_date=start_date,
        keyword=keyword
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
    formatted_summary = format_runs_summary_for_ui(summary)

    return {
        "runs": runs,
        "summary": formatted_summary,
    }


def get_single_run_summary(conn, run_id, metrics) -> dict:
    """ Build summary for single run. """

    df_raw = get_single_run_query(conn, run_id, metrics)

    if df_raw.empty:
        return {
            "run_id": run_id,
            "summary": None,
            "df": None,
        }
    else:
        df_summary = render_single_run_report(df_raw)
        row = df_summary.iloc[0]
        summary = {
            "duration_sec": row["Duration"],
            "distance_km": row["Distance (km)"],
            "avg_power": row["Avg Power"],
            "avg_ground_time": row["Avg Ground Time"],
            "avg_lss": row["Avg LSS"],
            "avg_cadence": row["Avg Cadence"],
            "avg_vo": row["Avg Vertical Osc."],
        }

    return {
        "run_id": run_id,
        "summary": summary,
        "df": row,  # optional if you want charts/table later
    }