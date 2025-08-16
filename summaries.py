from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import pandas as pd
from utils import print_table, get_default_timezone



def _fmt_hms(total_seconds: int) -> str:
    total_seconds = int(total_seconds or 0)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def _fmt_pace(sec_per_km: float | None) -> str:
    if not sec_per_km or sec_per_km <= 0:
        return "-"
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km % 60))
    return f'{m}:{s:02}"/km'


def _get_summary_bounds_local(mode: str, tz_str: str):
    """
    Return (start_local, end_local) for the last fully completed week OR last 7 days:
    Monday 00:00:00 -> Sunday 23:59:59 (local time) or last 7 days from today's date.
    """
    tz = ZoneInfo(tz_str)
    now_local = datetime.now(tz)
    today = now_local.date()

    if mode == "week_completed":
        # Last completed Mon–Sun
        weekday = today.weekday()  # Mon=0
        last_sun = today - timedelta(days=weekday + 1)
        last_mon = last_sun - timedelta(days=6)

        start_local = datetime.combine(last_mon, time.min, tzinfo=tz)
        end_local = datetime.combine(last_sun + timedelta(days=1), time.min, tzinfo=tz)

        wk = last_mon.isocalendar().week
        label = f"Week {wk} ({last_mon:%b %d}–{last_sun:%b %d})"

    elif mode == "rolling_7d":
        # Last 7 full days up to today
        end_local = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)
        start_local = end_local - timedelta(days=7)
        label = f"Last 7 days ({start_local:%b %d}–{(end_local - timedelta(seconds=1)):%b %d})"

    elif mode == "rolling_4w":
        # Last 4 weeks (28 days) up to today
        end_local = datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz)
        start_local = end_local - timedelta(days=28)
        label = f"Last 4 weeks ({start_local:%b %d})-{(end_local - timedelta(seconds=1)):%b %d}"

    else:
        raise ValueError("Unsupported mode. Use 'week_completed' or 'rolling_7d'.")

    # Convert to UTC strings matching DB format
    fmt = "%Y-%m-%d %H:%M:%S"
    return start_local.astimezone(ZoneInfo("UTC")).strftime(fmt), \
        end_local.astimezone(ZoneInfo("UTC")).strftime(fmt), \
        label


def _to_utc_string(dt_local):
    """Convert aware local dt -> UTC string matching DB format 'YYYY-MM-DD HH:MM:SS'."""
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
    return dt_utc.isoformat(sep=' ', timespec='seconds')


def get_period_summary(conn, mode, tz_name):
    """
    Returns a dict with week-level aggregates and a small per-run table.
    Pulls runs in the last completed local week OR last 7 days (converted to UTC for filtering),
    and joins per-run distance from metrics (MAX(stryd_distance)).
    """
    start_utc, end_utc, label = _get_summary_bounds_local(mode ,tz_name)

    # --- SQL: runs in range (UTC), join distance from runs, plus workout info ---
    # runs.datetime is stored in UTC.

    query = """
        SELECT 
            r.id AS run_id,
            r.datetime AS datetime_utc,
            r.avg_power,
            r.duration_sec,
            r.distance_m AS meters,
            r.avg_hr,
            w.workout_name,
            wt.name AS workout_type
        FROM runs r
        JOIN workouts w ON r.workout_id = w.id
        LEFT JOIN workout_types wt ON w.workout_type_id = wt.id
        WHERE r.datetime BETWEEN ? AND ?
        ORDER BY r.datetime
        """
    df = pd.read_sql(query, conn, params=(start_utc, end_utc))

    # If no runs, return empty summary
    if df.empty:
        return {
            "label": label,
            "period_utc": (start_utc, end_utc),
            "totals": {"runs": 0, "time_hms": "00:00:00","avg_power": 0, "km": 0.00, "avg_hr": None, "longest_km": 0.00},
            "per_run": df  # empty
        }

    # --- Aggregates (you can tweak these) ---
    df["km"] = df["meters"].fillna(0) / 1000.0

    ap = pd.to_numeric(df.get("avg_power"), errors="coerce")
    avg_power_num = float(ap.dropna().mean()) if ap.notna().any() else None

    # total time
    total_sec = int(df["duration_sec"].fillna(0).sum())
    time_hms = _fmt_hms(total_sec)

    # weighted avg HR by duration (ignore null HR rows)
    dur = df["duration_sec"].fillna(0)
    hr = df["avg_hr"]
    if hr.notna().any() and dur.sum() > 0:
        avg_hr = int(round((hr.fillna(0) * dur).sum() / dur.where(hr.notna(), 0).sum()))
    else:
        avg_hr = None

    longest_km = df["km"].max()
    total_km = round(df["km"].sum(), 2)

    return {
        "label": label,
        "period_utc": (start_utc, end_utc),
        "totals": {
            "runs": int(len(df)),
            "time_hms": time_hms,
            "avg_power": avg_power_num,
            "km": total_km,
            "avg_hr": avg_hr,
            "longest_km": round(float(longest_km), 2),
        },
        "per_run": df[["datetime_utc", "avg_power", "workout_name", "workout_type", "km", "duration_sec", "avg_hr", "run_id"]],

    }


# Map summary variants to canonical internal names
def _normalize_summary_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Accept common variants from summary SQL
    rename_map = {
        "datetime_utc": "datetime",
        "date_time": "datetime",
        "workout": "workout_name",
        "name": "workout_name",
        "type": "workout_type",
        "meters": "distance_m",
        "km": "distance_km",          # if summary already gave km
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # Ensure we have distance in meters as the working column
    if "distance_m" not in df.columns:
        if "distance_km" in df.columns:
            df["distance_m"] = df["distance_km"] * 1000.0
        else:
            df["distance_m"] = 0.0

    # Ensure duration_sec exists (some queries might format duration already)
    if "duration_sec" not in df.columns and "duration" in df.columns and df["duration"].dtype == "int64":
        df["duration_sec"] = df["duration"]

    # Format datetime to display as view command
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    return df


def summary_df(runs_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if runs_df is None or runs_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = _normalize_summary_columns(runs_df)

    # numeric source columns
    df["Distance (km)"] = (df["distance_m"].fillna(0) / 1000).round(2)
    df["Duration"] = df["duration_sec"].fillna(0).astype(int).apply(_fmt_hms)
    df["DateTime"] = pd.to_datetime(df["datetime"])  # keep full timestamp like view
    df["Workout Name"] = df.get("workout_name", "")
    df["Avg HR"] = df.get("avg_hr", pd.Series([None] * len(df)))
    df["Workout Type"] = df.get("workout_type", "")
    df["Avg Power (num)"] = pd.to_numeric(df.get("avg_power", pd.Series([None] * len(df))), errors="coerce")

    # formated display column
    df["Avg Power"] = df["Avg Power (num)"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "-")

    # By‑run table with the exact columns/order used by view
    by_run = df[["DateTime", "Workout Name","Distance (km)", "Duration", "Avg Power", "Avg HR", "Workout Type"]].copy()

    # overview row
    total_km = df["Distance (km)"].sum().round(2)
    total_runs = len(df)
    total_sec = int(df["duration_sec"].sum())

    avg_hr = int(round(df["Avg HR"].dropna().mean())) if df["Avg HR"].notna().any() else None
    avg_power_overall = df["Avg Power (num)"].dropna().mean()
    avg_power_overall_str = f"{avg_power_overall:.2f}" if pd.notna(avg_power_overall) else "-"
    avg_pace = total_sec / total_km
    avg_pace_str = _fmt_pace(avg_pace)

    overview = pd.DataFrame([{
        "Runs": total_runs,
        "Total Dist (km)": total_km,
        "Avg Power (w/kg)": avg_power_overall_str,
        "Total Time": _fmt_hms(total_sec),
        "Avg Pace": avg_pace_str,
        "Avg HR": avg_hr if avg_hr is not None else "-"
    }])

    return overview, by_run


def _show_summary(conn, mode: str, tz: str):
    summary = get_period_summary(conn, mode=mode, tz_name=tz)
    title = summary["label"]
    if summary["totals"]["runs"] == 0:
        print(f"❌ No runs found for {title}")
        return
    df_runs = summary["per_run"]
    overview, by_run = summary_df(df_runs)

    # 🌍 convert the displayed DateTime (stored UTC) to local for output
    if "DateTime" in by_run.columns:
        dt = pd.to_datetime(by_run["DateTime"], utc=True, errors="coerce")
        by_run["DateTime"] = dt.dt.tz_convert(ZoneInfo(tz)).dt.strftime("%Y-%m-%d %H:%M")
        by_run.rename(columns={"DateTime": f"DateTime ({tz})"}, inplace=True)
    print_summary(overview, by_run, title=title)


def print_summary(overview: pd.DataFrame, by_run: pd.DataFrame, title: str):
    print(f"\n🗓️ {title}")
    if overview.empty and by_run.empty:
        print("❌ No runs found for this period.")
        return
    print_table(overview)
    if not by_run.empty:
        by_run["Distance (km)"] = pd.to_numeric(by_run["Distance (km)"], errors="coerce")
        print("\n📋 Runs")
        print_table(by_run)

def summary_menu(conn):

    tz = get_default_timezone()
    while True:
        choice = input(
            "Choose a summary you are interested in:\n"
            "[1] Weekly summary\n"
            "[2] Rolling 4 week summary\n"
            "[3] Back\n> "
        ).strip()
        if choice == "1":
            while True:
                choice2 = input(
                    "Choose a summary you are interested in:\n"
                    "[1] Last complete Monday - Sunday\n"
                    "[2] Last 7 days from today\n"
                    "[3] Back\n> "
                ).strip()
                if choice2 == "1":
                    _show_summary(conn, "week_completed", tz=tz)

                elif choice2 == "2":
                    _show_summary(conn, "rolling_7d", tz=tz)

                elif choice2 == "3":
                    break
                else:
                    print("Invalid choice, try again.")

        elif choice == "2":
            _show_summary(conn, "rolling_4w", tz=tz)

        elif choice == "3":
            break

        else:
            print("Invalid choice, try again.")

    conn.close()