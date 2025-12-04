from datetime import timedelta, datetime, time, date
from zoneinfo import ZoneInfo
import pandas as pd
from pandas.core.interchange.dataframe_protocol import DataFrame

from stryder_core.date_utilities import as_local_date
from stryder_core.queries import fetch_runs_for_window
from stryder_core.utils_formatting import fmt_hms
from stryder_core.metrics import align_df_to_metric_keys

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
    df = pd.read_sql(fetch_runs_for_window(),
        conn, params=(start_utc, end_utc))

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


def custom_dates_report(
        conn,
        tz_name: str,
        mode: str, *,
        end_date: datetime | None = None,
        start_date: datetime | None = None
) -> tuple[str, DataFrame]:

    # Validation
    have_range = (start_date is not None) and (end_date is not None)
    if not have_range:
        raise ValueError("Provide start_date+end_date.")

    # Normalize date → datetime if needed
    if isinstance(start_date, date) and not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, time.min)

    if isinstance(end_date, date) and not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, time.min)

    # Get bounds calculation
    start_utc, end_utc, label = get_report_bounds(
        mode=mode,
        tz_name=tz_name,
        weeks=1,
        end_date=end_date,
        start_date=start_date,
    )
    # SQL fetch for the entire window
    df = pd.read_sql(fetch_runs_for_window(),
        conn, params=(start_utc, end_utc))

    if df.empty:
        cols = ["start_date", "end_date", "runs", "distance_km", "duration_sec", "avg_power", "avg_hr"]
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

    # Get start date and end date in local timezone
    start_local = pd.Timestamp(start_utc, tz="UTC").tz_convert(tz)
    end_local = pd.Timestamp(end_utc, tz="UTC").tz_convert(tz) - timedelta(seconds=1)

    # Aggregate per custom window
    agg = df.agg({
        "run_id": "count",
        "km":"sum",
        "duration_sec":"sum",
        "avg_power":"mean",
        "avg_hr":"mean"
    })

    # RAW canonical names
    summary = agg.rename({
            "run_id": "runs",
            "km": "distance_km",
            "duration_sec": "duration_sec",
            "avg_power": "avg_power",
            "avg_hr": "avg_hr",
        }).to_frame().T
    # Add date columns
    summary["start_date"] = start_local.date()
    summary["end_date"] = end_local.date()

    # Reorder columns
    summary = summary[[
        "start_date", "end_date",
        "runs", "distance_km", "duration_sec",
        "avg_power", "avg_hr",
    ]]
    return label, summary


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
    """ Return the first matching column from a list of candidate names, or a default, otherwise raise KeyError. """
    for c in candidates:
        if c in df.columns:
            return df[c]
    if default is not None:
        return default
    raise KeyError(f"None of {candidates} found in DF columns: {list(df.columns)}")


def render_single_run_report(df:pd.DataFrame) -> pd.DataFrame:
    """ Takes a df, gets run ID, calculates duration in seconds and distance in meters,
     then builds the single run report and then returns the df """
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