import logging
import pandas as pd
from datetime import timedelta
from date_utilities import resolve_tz, to_utc
from metrics import align_df_to_metric_keys, STRYD_PARSE_SPEC, GARMIN_PARSE_SPEC

PARSE_STRYD_CSV_KEYS = {"timestamp_s", "str_dist_m", "str_speed", "power_sec", "ground",
        "cadence", "vo", "stiffness", "ts_local", "delta_s", "dist_delta", "wt_name" }

PARSE_GARMIN_CSV_KEYS = {"date", "wt_name", "avg_hr"}

class ZeroStrydDataError(Exception):
    """Raised when Stryd CSV has zero speed/distance for the entire file."""
    pass


def is_stryd_all_zero(df: pd.DataFrame) -> bool:
    # Prefer speed check
    if "str_speed" in df.columns:
        spd = pd.to_numeric(df["str_speed"], errors="coerce").fillna(0)
        if (spd.abs() < 1e-12).all():
            return True
    # Fallback: distance column if present
    if "str_dist_m" in df.columns:
        dist = pd.to_numeric(df["str_dist_m"], errors="coerce").fillna(0)
        if float(dist.max()) <= 0.0:
            return True
    return False


def edit_stryd_csv(df, timezone_str: str | None = None):
    """ Takes stryd.csv columns,normalises them, turns time to local, gets distance from speed, returns df """

    # Normalize stryd.csv headers → canonical keys
    df = align_df_to_metric_keys(df, STRYD_PARSE_SPEC, keys=PARSE_STRYD_CSV_KEYS)

    # Convert Unix timestamps to local time using user-specified timezone
    df['ts_local'] = pd.to_datetime(df['timestamp_s'], unit='s', utc=True)\
                      .dt.tz_convert(resolve_tz(timezone_str))

    # Move the Local Timestamp to the first column
    if "ts_local" in df.columns:
        col = df.pop("ts_local")
        df.insert(0, "ts_local", col)

     # Sort by time & compute time delta (sec)
    df = df.sort_values('ts_local').reset_index(drop=True)
    df['delta_s'] = df['ts_local'].diff().dt.total_seconds().fillna(0)
    df["delta_s"] = df["delta_s"].clip(lower=0)  # avoid negatives

    # Distance from Stryd speed, if present
    if "str_speed" in df.columns:
        spd = pd.to_numeric(df["str_speed"], errors="coerce").fillna(0.0)

        # per-row distance (m) = speed(m/s) * delta(s)
        df["dist_delta"] = spd * df["delta_s"]

        # cumulative Stryd distance (m)
        df["str_dist_m"] = df["dist_delta"].cumsum()

        # sanity check for all-zero speed
        if (spd.abs() < 1e-12).all():
            logging.warning("⚠️  Stryd CSV appears to have zero speed everywhere.")
    else:
        # keep columns consistent even if speed missing
        df["dist_delta"] = 0.0
        df["str_dist_m"] = 0.0
    return df


def normalize_workout_type(raw_name):
    """ Checks keywords in workout name to assign to workout type """
    if isinstance(raw_name, pd.Series):
        raw_name = raw_name.iloc[0]
    name = str(raw_name).lower()
    if "ez" in name or "easy" in name:
        return "Easy Run"
    elif "long" in name:
        return "Long Run"
    elif "threshold" in name or "vo2" in name or "intervals" in name:
        return "Intervals"
    elif "test" in name or "testing" in name or "trial" in name or "tt" in name:
        return "Testing"
    elif "race" in name:
        return "Race"
    else:
        logging.warning(f"❓ Unknown workout type for: {raw_name}")
        return "Other"


def get_matched_garmin_row(stryd_df, garmin_df, timezone_str: str | None = None, tolerance_sec: int = 60):
    """ Checks if stryd_df and garmin_df match in datetime, if yes return the row of the matched date """
    tz = resolve_tz(timezone_str)

    # Stryd start time → UTC
    stryd_start_utc = to_utc(stryd_df.loc[0, "ts_local"], in_tz=tz)
    logging.debug(f"STRYD start UTC: {stryd_start_utc!r}")

    # Normalize garmin.csv headers with canonical names
    g = garmin_df.copy()
    g.columns = g.columns.str.strip()
    g = align_df_to_metric_keys(g, GARMIN_PARSE_SPEC, keys=PARSE_GARMIN_CSV_KEYS)

    # Convert Garmin 'date' to datetime
    g["date"] = pd.to_datetime(g["date"], errors="coerce")
    g["date_utc"] = g["date"].apply(lambda dt: to_utc(dt, in_tz=tz))
    logging.debug("Sample Garmin dates (local & utc):")
    logging.debug(g[["date", "date_utc"]].head().to_string())

    # Find the closest Garmin row within tolerance
    tol = timedelta(seconds=tolerance_sec)
    diffs = (g["date_utc"] - stryd_start_utc).abs() # type: ignore
    mask = diffs <= tol

    logging.debug(f"Min diff: {diffs.min()}")
    logging.debug(f"Any within tolerance ({tolerance_sec}s)? {mask.any()}")

    if not mask.any():
        return None

    idx = diffs[mask].idxmin()
    return g.loc[idx]


def calculate_duration(stryd_df):

    if 'ts_local' not in stryd_df.columns:
        raise ValueError("DataFrame must contain a 'ts_local' column.")

    start_time = stryd_df['ts_local'].iloc[0]
    end_time = stryd_df['ts_local'].iloc[-1]

    duration = end_time - start_time

    # Format duration as string (without days, if present)
    duration_str = str(duration)
    if "day" in duration_str:
        duration_str = str(timedelta(seconds=duration.total_seconds() % 86400))  # 86400 = seconds in a day

    # Store formatted duration in the DataFrame
    stryd_df['duration_sec'] = duration_str

    return stryd_df, duration, duration_str