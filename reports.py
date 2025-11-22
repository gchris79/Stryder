from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from date_utilities import as_local_date, to_utc, dt_to_string, input_date
from formatting import fmt_hms, fmt_str_decimals
from metrics import align_df_to_metric_keys
from queries import view_menu
from runtime_context import get_tzinfo, get_tz_str
from utils import prompt_menu, MenuItem, input_positive_number, \
    get_valid_input
from visualizations import display_menu

SINGLE_RUN_SAMPLE_KEYS = {"power_sec", "ground", "lss", "cadence", "vo"}


def weekly_report(
        conn,
        tz_name: str,
        mode: str, *,
        weeks: int | None = None,
        end_date: datetime | None = None,
        start_date: datetime | None = None
) -> tuple[str, pd.DataFrame]:

    """ One of a) weeks (optionally with end date
               b) custom with start_date and end_date"""

    # Validation
    have_weeks = weeks is not None
    have_range = (start_date is not None) and (end_date is not None)
    if have_weeks == have_range:
        raise ValueError("Provide either weeks (±end_date) OR start_date+end_date.")


    # Get bounds calculation
    start_utc, end_utc, label = get_report_bounds(
        mode=mode,
        tz_name=tz_name,
        weeks=weeks,
        end_date=end_date,
        start_date=start_date,
        )

    # SQL fetch for the entire window
    df = pd.read_sql(
        """
        SELECT 
            r.id AS run_id,
            r.datetime AS datetime_utc,
            r.duration_sec,
            r.distance_m AS meters,
            r.avg_power,
            r.avg_hr,
            w.workout_name,
            wt.name AS workout_type
        FROM runs r
        JOIN workouts w ON r.workout_id = w.id
        LEFT JOIN workout_types wt ON w.workout_type_id = wt.id
        WHERE r.datetime BETWEEN ? AND ?
        ORDER BY r.datetime
        """,
        conn, params=(start_utc, end_utc)
    )

    if df.empty:
        cols = ["week_start", "week_end", "runs", "distance_km", "duration_sec", "avg_power", "avg_hr"]
        return label, pd.DataFrame(columns=cols)

    # guard to avoid duplicates
    if "run_id" in df.columns:
        df = df.drop_duplicates(subset=["run_id"], keep="first")

    tz = ZoneInfo(tz_name)

    # Make DateTime tz-aware & convert to local
    dt = pd.to_datetime(df["datetime_utc"], utc=True, errors="coerce")
    df["dt_local"] = dt.dt.tz_convert(tz)

    # Working columns
    df["km"] = (df["meters"].fillna(0) / 1000.0)
    df["duration_sec"] = df["duration_sec"].fillna(0).astype(int)

    # 7-day buckets anchored at the window start (local)
    start_local = pd.Timestamp(start_utc, tz="UTC").tz_convert(tz)
    days_since = (df["dt_local"].dt.floor("D") - start_local).dt.days
    week_idx = (days_since // 7)
    df = df.assign(week_idx=week_idx).query("week_idx >= 0") # guard for the possibility of bad datetime out of bounds

    # Aggregate per week
    agg = (df.groupby("week_idx")
             .agg(Runs=("run_id", "count") if "run_id" in df.columns else ("dt_local","count"),
                  km=("km","sum"),
                  sec=("duration_sec","sum"),
                  pow=("avg_power","mean"),
                  HR=("avg_hr","mean"))
             .reset_index())

    agg["week_start"] = agg["week_idx"].map(lambda i: start_local + timedelta(days=7 * int(i)))
    agg["week_end"] = agg["week_start"] + timedelta(days=7)

    # RAW canonical names
    weekly_raw = (
        agg.rename(columns={
            "Runs": "runs",
            "km": "distance_km",
            "sec": "duration_sec",
            "pow": "avg_power",
            "HR": "avg_hr",
        })
        .sort_values("week_start")
        [["week_start", "week_end", "runs", "distance_km", "duration_sec", "avg_power", "avg_hr"]]
    )

    return label, weekly_raw


def get_report_bounds(
        mode: str,
        tz_name:str,
        *,
        weeks:int,
        end_date: datetime | None,
        start_date: datetime | None,
):
    """
    Return (start_local, end_local) for the last fully completed week OR last 7 days:
    Monday 00:00:00 -> Sunday 23:59:59 (local time) or last 7 days from today's date.
    """
    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz).date()

    # Normalize inputs to date
    if start_date is not None:
        start_date = as_local_date(start_date, tz)
    if end_date is not None:
        end_date = as_local_date(end_date, tz)

    # --- Custom absolute range (start + end) ---
    if start_date is not None and end_date is not None:
        # inclusive of end_date: make end_local = next day 00:00
        start_local = datetime.combine(start_date, time.min, tzinfo=tz)
        end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        label = (f"{start_local:%b %d} – "
                 f"{(end_local - timedelta(seconds=1)):%b %d}")
    else:
        # --- Relative windows (weeks) ---
        if weeks is None or weeks <= 0:
            raise ValueError("For relative windows, provide weeks >= 1.")

        # pick anchor day (the 'end' of the window)
        anchor_day = end_date or today_local

        if mode == "calendar":
            # Monday of the anchor week
            anchor_monday = anchor_day - timedelta(days=anchor_day.weekday())  # Monday 00:00 of anchor week
            end_monday = anchor_monday      # last completed boundary
            start_monday = end_monday - timedelta(days=7 * weeks)

            start_local = datetime.combine(start_monday, time.min, tzinfo=tz)
            end_local = datetime.combine(end_monday, time.min, tzinfo=tz)

            # Nice label covering the whole span
            if weeks != 1:
                label = (f"{weeks} calendar weeks "
                     f"({start_local:%b %d} "
                         f"– {(end_local - timedelta(seconds=1)):%b %d})")
            else: label = (f"{weeks} calendar week "
                     f"({start_local:%b %d} – {(end_local - timedelta(seconds=1)):%b %d})")

        elif mode == "rolling":
            # rolling = any 7-day windows; here we just give a continuous N*7 days window
            end_local = datetime.combine(anchor_day + timedelta(days=1), time.min, tzinfo=tz)
            start_local = end_local - timedelta(days=7 * weeks)
            if weeks != 1:
                label = (f"{weeks} rolling weeks "
                         f"({start_local:%b %d} – {(end_local - timedelta(seconds=1)):%b %d})")
            else:
                label = (f"{weeks} rolling week "
                         f"({start_local:%b %d} – {(end_local - timedelta(seconds=1)):%b %d})")
        else:
            raise ValueError("Unsupported mode. Use 'calendar' or 'rolling'.")

     # Convert to UTC strings for DB
    fmt = "%Y-%m-%d %H:%M:%S"
    start_utc = start_local.astimezone(ZoneInfo("UTC")).strftime(fmt)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).strftime(fmt)
    return start_utc, end_utc, label


def get_single_run_query(conn, run_id: int, metrics: dict):
    """ Creates query for single run report returns dataframe of that query """
    query = """
        SELECT
            m.id,
            m.run_id,
            m.datetime          AS dt,
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
    df_raw = pd.read_sql(query, conn, params=(run_id,), parse_dates=["dt"])

    # Ensure that dt is datetime object and not string
    df_raw["dt"] = pd.to_datetime(df_raw["dt"], errors="coerce")

    # Ensure that columns are numeric
    for c in ["power", "stryd_distance", "ground_time", "stiffness", "cadence", "vertical_oscillation"]:
        df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")

    # Rename the SQL column names to metrics canonical keys
    df = align_df_to_metric_keys(df_raw, metrics, keys=SINGLE_RUN_SAMPLE_KEYS)

    if "stryd_distance" in df.columns and "distance" in metrics:
        df = df.rename(columns={"stryd_distance": "distance_m"})

    if "elapsed_sec" not in df.columns:
        df["elapsed_sec"] = (df["dt"] - df["dt"].iloc[0]).dt.total_seconds()
    if "distance_m" in df.columns and "distance_km" not in df.columns:
        df["distance_km"] = df["distance_m"] / 1000.0

    if "run_id" not in df.columns:
        df["run_id"] = int(run_id)

    return df


def first_col(df: pd.DataFrame, *candidates: str, default=None):
    for c in candidates:
        if c in df.columns:
            return df[c]
    if default is not None:
        return default
    raise KeyError(f"None of {candidates} found in DF columns: {list(df.columns)}")


def render_single_run_report(df:pd.DataFrame) -> pd.DataFrame:
    run_id = int(first_col(df, "run_id", "id").iloc[0])
    # Calculate duration from datetime
    duration_sec = int((df["dt"].max() - df["dt"].min()).total_seconds())
    # Calculate total distance and format in km
    distance_m = float(first_col(df, "distance_m", "stryd_distance", default=0).max() or 0.0)

    # Building the report df
    row = {
        "Run ID": run_id,
        "Duration": fmt_hms(duration_sec),
        "Distance (km)": round(distance_m / 1000.0, 2),
        "Avg Power": round(first_col(df, "power_sec", "power").mean(), 1),
        "Avg Ground Time": round(first_col(df, "ground").mean(), 1),
        "Avg LSS": round(first_col(df, "lss", "stiffness").mean(), 1),
        "Avg Cadence": round(first_col(df, "cadence").mean(), 1),
        "Avg Vertical Osc.": round(first_col(df, "vo", "vertical_oscillation").mean(), 2),
    }
    return pd.DataFrame([row])


def reports_menu(conn, metrics):

    tz = get_tz_str()
    tzinfo = get_tzinfo()

    items1 = [
        MenuItem("1", "Last N weeks"),
        MenuItem("2", "N weeks ending on a date of your choice"),
        MenuItem("3", "Custom date range"),
        MenuItem("4", "Single run report")
    ]

    items2 = [
        MenuItem("1", "Rolling weeks (seven days from this day)"),
        MenuItem("2", "Calendar weeks (Monday - Sunday)" ),
    ]

    choice1 = prompt_menu("Reports", items1)
    # Fork for the type of the report single or batch
    if choice1 in ["1","2","3"]:
        df_type = "batch"
        # 1) Last N weeks
        if choice1 == "1":
            choice2 = prompt_menu("Group the weeks as", items2)
            if choice2 in ["1", "2"]:
                weeks = input_positive_number("How many weeks? ")
                mode = "rolling" if choice2 == "1" else "calendar"
                label, weekly_raw = weekly_report(conn, tz, mode=mode, weeks=weeks)
                display_menu(label, weekly_raw, df_type, metrics)

            elif choice1 == "b":
                return
            elif choice1 == "q":
                exit(0)

        # N weeks ending on a date of your choice
        elif choice1 == "2":
            choice2 = prompt_menu("Group the weeks as", items2)
            if choice2 in ["1", "2"]:
                weeks = input_positive_number("How many weeks? ")
                end_date = input("Give the end date of the report (YYYY-MM-DD): ")
                end_dt = to_utc(end_date, in_tz=tzinfo)
                mode = "rolling" if choice2 == "1" else "calendar"
                label, weekly_raw = weekly_report(conn, tz, mode=mode, weeks=weeks, end_date=end_dt)
                display_menu(label, weekly_raw, df_type, metrics)

            elif choice1 == "b":
                return
            elif choice1 == "q":
                exit(0)

        # Custom date range
        elif choice1 == "3":
            str_dt = input_date("Give the start date of the report (YYYY-MM-DD): ")
            end_dt = input_date("Give the end date of the report (YYYY-MM-DD): ")
            label, weekly_raw = weekly_report(conn, tz, mode="rolling", start_date=str_dt, end_date=end_dt)
            display_menu(label, weekly_raw, df_type, metrics)

    elif choice1 == "4":
        # Single run report
        df_type = "single"

        if (result := view_menu(conn, metrics,"for_report")) is None:      # Guard if user hits back without choosing run
            return                                           # Return to previous menu safely
        rows, columns = result              # Unpack safely

        cool_string = None
        if (run_id := get_valid_input("Please enter Run ID for the run you are interested in: ")) is None:
            return

        for row in rows:                    # Check users choice to match the run in table
            if int(row["run_id"]) == int(run_id):
                raw_ts = row["datetime"]                   # take the datetime of the run...
                dt_local = dt_to_string(to_utc(raw_ts, in_tz=tzinfo), "ymd_hms", tz=tzinfo)      # ...and localize it for display in cool string
                cool_string = (
                    f'\nRun {row["run_id"]} | {dt_local} | '
                    f'{row["wt_name"]} | {fmt_str_decimals(row["distance_m"]/1000)} km | {fmt_hms(row["duration"])}'
                )
                print(cool_string)      # print a cool string to show details about the picked run before the report

                df_raw = get_single_run_query(conn, run_id, metrics)
                if df_raw.empty:
                    print(f"Empty dataframe.")
                    return
                display_menu("",df_raw, df_type, metrics)
                break
        if cool_string is None:
            print(f"\nRun with Run ID {run_id} does not exist in you database.\n")

    elif choice1 == "b":
        return
        #menu_guard(None)

    elif choice1 == "q":
        exit(0)