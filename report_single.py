import pandas as pd
from utils import print_table, fmt_seconds_to_hms


def get_single_run_query(conn, run_id):
    query = """
        SELECT
            m.id,
            m.run_id,
            m.datetime AS dt,
            m.power,
            m.stryd_distance,
            m.ground_time,
            m.stiffness,
            m.cadence,
            m.vertical_oscillation
        FROM metrics m 
        JOIN runs r ON m.run_id = r.id
        WHERE m.run_id = ? 
        ORDER BY m.datetime ASC
    """
    df = pd.read_sql(query, conn, params=(run_id,), parse_dates=["dt"])

    # Ensure that dt is datetime object and not string
    df["dt"] = pd.to_datetime(df["dt"], errors="coerce")

    # Ensure that columns are numeric
    for c in ["power", "stryd_distance", "ground_time", "stiffness", "cadence", "vertical_oscillation"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def render_single_run_report(df: pd.DataFrame) -> pd.DataFrame:

    run_id = int(df["run_id"].iloc[0])

    # Calculate duration from datetime
    duration_sec = (df["dt"].max() - df["dt"].min()).total_seconds()

    # Calculate total distance and format in km
    distance_km = (df["stryd_distance"].max() or 0) / 1000.0

    # Building the report df
    report = pd.DataFrame([{
        "run_id": run_id,
        "Duration": fmt_seconds_to_hms(duration_sec),
        "Distance (km)" : round(distance_km, 2),
        "Avg Power" : round(df["power"].mean(),1),
        "Avg Ground Time" : round(df["ground_time"].mean(),1),
        "Avg LSS" : round(df["stiffness"].mean(), 1),
        "Avg Cadence" : round(df["cadence"].mean(), 1),
        "Avg Vertical Osc." : round(df["vertical_oscillation"].mean(), 2),

    }])
    return report


def single_report_menu(conn,run_id):
    df = get_single_run_query(conn,run_id)
    if df.empty:
        print(f"No samples found for run_id={run_id}.")
        return
    single_run = render_single_run_report(df)
    print_table(single_run)