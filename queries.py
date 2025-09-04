import pandas as pd
from utils import get_default_timezone, print_table, fmt_sec_to_hms, MenuItem, prompt_menu
from zoneinfo import ZoneInfo

pd.set_option('display.max_rows', None)  # show all rows
pd.set_option('display.max_columns', None) # show all columns
pd.set_option('display.width', 150)


def format_df_columns(df):
    """ Format the columns of the dataframe for display """

    if df is None or getattr(df, "empty", True):
        print("ℹ️ No results.")


    # Format distance → km
    if "distance (m)" in df.columns:
        df["Distance (km)"] = (df["distance (m)"].fillna(0) / 1000).round(2)
        df.drop(columns=["distance (m)"], inplace=True)

    # Format duration
    if "duration_sec" in df.columns:
        df["Duration"] = df["duration_sec"].fillna(0).astype(int).apply(fmt_sec_to_hms)
        df.drop(columns=["duration_sec"], inplace=True)


    # Check if there is a DateTime field → local (if present)
    tz = get_default_timezone() or "Europe/Athens"
    dt_col = next(
        (c for c in df.columns if c.lower().replace(" ", "") in {"datetime", "date"}),
        None,
    )
    if dt_col:
        try:
            df.sort_values(by=dt_col, inplace=True)
        except Exception:
            pass
        dt = pd.to_datetime(df[dt_col], utc=True, errors="coerce")
        df[dt_col] = dt.dt.tz_convert(ZoneInfo(tz)).dt.strftime("%Y-%m-%d %H:%M")
        df.rename(columns={dt_col: f"DateTime ({tz})"}, inplace=True)

    df_view = df[[f"DateTime ({tz})", "Workout Name", "Distance (km)", "Duration", "Avg Power (w/kg)", "Avg HR", "Workout Type"]].copy()
    return df_view


def render_workouts(df):
    """Format then print a workouts DataFrame."""

    df_fmt = format_df_columns(df)
    if df_fmt is not None and not df_fmt.empty:
        print_table(df_fmt)
    else:
        print("ℹ️ No results.")


def get_base_workouts_query():
    return """
        SELECT 
            r.datetime AS "DateTime",
            w.workout_name AS "Workout Name",
            r.distance_m AS 'distance (m)',
            r.duration_sec,
            r.avg_power AS "Avg Power (w/kg)",
            r.avg_hr AS "Avg HR",
            wt.name AS "Workout Type"
        FROM runs r
        JOIN workouts w ON r.workout_id = w.id
        JOIN workout_types wt ON w.workout_type_id = wt.id
    """


# Return all workouts
def get_all_workouts(conn):
    query = get_base_workouts_query() + " ORDER BY r.datetime"
    return pd.read_sql(query, conn)


# Return workouts filtered by date
def get_workouts_bydate(date1, date2, conn):
    query = get_base_workouts_query() + "WHERE r.datetime BETWEEN ? AND ? ORDER BY r.datetime"
    return pd.read_sql(query, conn, params=(date1, date2))


# Return workouts filtered by keyword
def get_workout_by_keyword(keyword,conn):
    query = get_base_workouts_query() + """
        WHERE w.workout_name LIKE ? 
            OR wt.name LIKE ?
        ORDER BY r.datetime
    """
    like_term = f"%{keyword}%"
    return pd.read_sql(query,conn, params=(like_term, like_term))


# View (command) menu
def view_menu(conn):

    items1 = [
        MenuItem("1", "All runs"),
        MenuItem("2", "Runs by date"),
        MenuItem("3", "Runs by keyword"),
    ]

    choice1 = prompt_menu("View Runs", items1)

    if choice1 == "1":
        df = get_all_workouts(conn)
        render_workouts(df)

    elif choice1 == "2":
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")
        start_full = f"{start_date} 00:00:00"
        end_full = f"{end_date} 23:59:59"
        df = get_workouts_bydate(start_full, end_full, conn)
        render_workouts(df)

    elif choice1 == "3":
        keyword = input("Search workouts by keyword: ")
        df = get_workout_by_keyword(keyword, conn)
        render_workouts(df)

    elif choice1 == "b":
        return

    elif choice1 == "q":
        exit(0)