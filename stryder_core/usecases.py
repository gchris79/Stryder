from datetime import date, timedelta
from stryder_core.metrics import build_metrics
from stryder_core.queries import fetch_page, views_query
from stryder_core.reports import custom_dates_report, get_single_run_query, compute_single_run_summary
from stryder_core.table_formatters import format_row_for_ui, format_runs_summary_for_ui
from stryder_core.utils_formatting import fmt_hms


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
        return {"run_id": run_id, "summary": None, "wt_name": None, "df": None}

    s = compute_single_run_summary(df_raw)
    wt_name = df_raw.iloc[0].get("wt_name") if "wt_name" in df_raw.columns else None
    dt = df_raw.iloc[0].get("dt") if "dt" in df_raw.columns else None

    summary = {
        "run_id": s["run_id"],
        "duration_sec": s["duration_sec"],
        "duration_hms": fmt_hms(s["duration_sec"]),
        "distance_km": round(s["distance_km"], 2),
        "avg_power": round(s["avg_power"], 1),
        "avg_ground_time": round(s["ground_time"], 1),
        "avg_lss": round(s["stiffness"], 1),
        "avg_cadence": round(s["cadence"], 1),
        "avg_vo": round(s["vertical_oscillation"], 2),
    }

    return {
        "run_id": run_id,
        "summary": summary,
        "dt": dt,
        "wt_name": wt_name,
        "df": df_raw,  # optional if you want charts/table later
    }