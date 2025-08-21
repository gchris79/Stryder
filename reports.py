from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from utils import get_default_timezone, prompt_menu, MenuItem, fmt_seconds_to_hms, input_positive_number, \
    string_to_datetime, as_date
from visualizations import display_menu


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
        return label, pd.DataFrame(columns=["week_start","week_end","Runs","Distance (km)","Duration","Avg Power", "Avg HR"])

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

    agg["week_start"] = agg["week_idx"].map(lambda i: start_local + timedelta(days=7*int(i)))
    agg["week_end"]   = agg["week_start"] + timedelta(days=7)

    agg["Distance (km)"] = agg["km"].round(2)
    agg["Duration"] = agg["sec"].apply(fmt_seconds_to_hms)

    agg["Avg Power"] = agg["pow"]
    agg["Avg HR"] = agg["HR"]

    weekly = agg.sort_values("week_start")[["week_start","week_end","Runs","Distance (km)","Duration","Avg Power", "Avg HR"]]
    return label, weekly    # week_start and week_end are daytime objects


def get_report_bounds(
        mode: str,
        tz_name:str,
        *,
        weeks:int,
        end_date: datetime,
        start_date: datetime,
):
    """
    Return (start_local, end_local) for the last fully completed week OR last 7 days:
    Monday 00:00:00 -> Sunday 23:59:59 (local time) or last 7 days from today's date.
    """
    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz).date()

    # Normalize inputs to date
    if start_date is not None:
        start_date = as_date(start_date)
    if end_date is not None:
        end_date = as_date(end_date)

    # --- Custom absolute range (start + end) ---
    if start_date is not None and end_date is not None:
        # inclusive of end_date: make end_local = next day 00:00
        start_local = datetime.combine(start_date, time.min, tzinfo=tz)
        end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        label = f"{start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d}"
    else:
        # --- Relative windows (weeks) ---
        if weeks is None or weeks <= 0:
            raise ValueError("For relative windows, provide weeks >= 1.")

        # pick anchor day (the 'end' of the window)
        anchor_day = end_date or today_local

        if mode == "calendar":
            # Monday of the anchor week
            anchor_monday = anchor_day - timedelta(days=anchor_day.weekday())  # Mon=0
            end_monday = anchor_monday + timedelta(days=7)  # next Monday 00:00
            start_monday = end_monday - timedelta(days=7 * weeks)  # N weeks back

            start_local = datetime.combine(start_monday, time.min, tzinfo=tz)
            end_local = datetime.combine(end_monday, time.min, tzinfo=tz)

            # Nice label covering the whole span
            if weeks != 1:
                label = (f"{weeks} calendar weeks "
                     f"({start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d})")
            else: label = (f"{weeks} calendar week "
                     f"({start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d})")

        elif mode == "rolling":
            # rolling = any 7-day windows; here we just give a continuous N*7 days window
            end_local = datetime.combine(anchor_day + timedelta(days=1), time.min, tzinfo=tz)
            start_local = end_local - timedelta(days=7 * weeks)
            if weeks != 1:
                label = (f"{weeks} calendar weeks "
                         f"({start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d})")
            else:
                label = (f"{weeks} calendar week "
                         f"({start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d})")
        else:
            raise ValueError("Unsupported mode. Use 'calendar' or 'rolling'.")

     # Convert to UTC strings for DB
    fmt = "%Y-%m-%d %H:%M:%S"
    start_utc = start_local.astimezone(ZoneInfo("UTC")).strftime(fmt)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).strftime(fmt)
    return start_utc, end_utc, label


def reports_menu(conn):

    tz = get_default_timezone()

    items1 = [
        MenuItem("1", "Last N weeks"),
        MenuItem("2", "N weeks ending on a date of your choice"),
        MenuItem("3", "Custom date range"),
    ]

    items2 = [
        MenuItem("1", "Rolling weeks (seven days from this day)"),
        MenuItem("2", "Calendar weeks (Monday - Sunday)" ),
    ]

    choice1 = prompt_menu("Reports", items1)

    # 1) Last N weeks
    if choice1 == "1":
        choice2 = prompt_menu("Group the weeks as", items2)
        if choice2 in ["1", "2"]:
            weeks = input_positive_number("How many weeks? ")
            mode = "rolling" if choice2 == "1" else "calendar"
            label, weekly = weekly_report(conn, tz, mode=mode, weeks=weeks)
            display_menu(label, weekly)

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
            end_dt = string_to_datetime(end_date)
            mode = "rolling" if choice2 == "1" else "calendar"
            label, weekly = weekly_report(conn, tz, mode=mode, weeks=weeks, end_date=end_dt)
            display_menu(label, weekly)

        elif choice1 == "b":
            return
        elif choice1 == "q":
            exit(0)

    # Custom date range
    elif choice1 == "3":
        start_date = input("Give the start date of the report (YYYY-MM-DD): ")
        str_dt = string_to_datetime(start_date)
        end_date = input("Give the end date of the report (YYYY-MM-DD): ")
        end_dt = string_to_datetime(end_date)
        label, weekly = weekly_report(conn, tz, mode="rolling", start_date=str_dt, end_date=end_dt)
        display_menu(label, weekly)

    elif choice1 == "b":
        return
    elif choice1 == "q":
        exit(0)