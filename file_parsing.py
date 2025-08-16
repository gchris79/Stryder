import logging
import pandas as pd
from datetime import timedelta
from zoneinfo import ZoneInfo
from utils import _resolve_tz


class ZeroStrydDataError(Exception):
    """Raised when Stryd CSV has zero speed/distance for the entire file."""
    pass


def _is_stryd_all_zero(df: pd.DataFrame) -> bool:
    # Prefer speed check
    if "Stryd Speed (m/s)" in df.columns:
        spd = pd.to_numeric(df["Stryd Speed (m/s)"], errors="coerce").fillna(0)
        if (spd.abs() < 1e-12).all():
            return True
    # Fallback: distance column if present
    if "Stryd Distance (meters)" in df.columns:
        dist = pd.to_numeric(df["Stryd Distance (meters)"], errors="coerce").fillna(0)
        if float(dist.max()) <= 0.0:
            return True
    return False


def load_csv(stryd_csv, garmin_csv):
    stryd_df = pd.read_csv(stryd_csv)
    garmin_df = pd.read_csv(garmin_csv)
    return stryd_df, garmin_df


def edit_stryd_csv(df, timezone_str: str | None = None):

    # Convert Unix timestamps to local time using user-specified timezone
    df['Local Timestamp'] = pd.to_datetime(
        df['Timestamp'], unit='s', utc=True
    ).dt.tz_convert(_resolve_tz(timezone_str))

    # Move the Local Timestamp to the first column
    cols = ['Local Timestamp'] + [col for col in df.columns if col != 'Local Timestamp']
    df = df[cols]

     # Calculates Stryd Distance from Stryd Speed
    df = df.sort_values('Local Timestamp').reset_index(drop=True)
    df['Time Delta'] = df['Local Timestamp'].diff().dt.total_seconds().fillna(0)
    df['Distance Delta'] = df['Stryd Speed (m/s)'] * df['Time Delta']
    df['Stryd Distance (meters)'] = df['Distance Delta'].cumsum()

    # Check Stryd speed if it returns 00.00 data
    spd_col = pd.to_numeric(df.get("Stryd Speed (m/s)"), errors="coerce").fillna(
        0) if "Stryd Speed (m/s)" in df.columns else None
    if spd_col is not None and (spd_col.abs() < 1e-12).all():
        logging.warning("⚠️  Stryd CSV appears to have zero speed everywhere.")
    return df


def normalize_workout_type(raw_name):
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

    tz = _resolve_tz(timezone_str)

    # Stryd start time → UTC
    stryd_start_time = stryd_df.loc[0, 'Local Timestamp']
    if stryd_start_time.tzinfo is None:
        stryd_start_time = stryd_start_time.replace(tzinfo=ZoneInfo("UTC"))
    else:
        stryd_start_time = stryd_start_time.astimezone(ZoneInfo("UTC"))

    # Garmin dates → ensure tz-aware, then to UTC
    g = garmin_df.copy()
    g.columns = g.columns.str.strip()
    if not pd.api.types.is_datetime64_any_dtype(g['Date']):
        g['Date'] = pd.to_datetime(g['Date'], format='%Y-%m-%d %H:%M:%S')
    if g['Date'].dt.tz is None:
        g['Date'] = g['Date'].dt.tz_localize(tz, ambiguous='infer').dt.tz_convert('UTC')

    tol = timedelta(seconds=tolerance_sec)

    # Find first row within tolerance
    for row in g.itertuples(index=False):
        if abs(row.Date - stryd_start_time) <= tol:
            # return the full Series so we can read any fields
            return g.loc[g['Date'] == row.Date].iloc[0]

    return None


def garmin_field(row, candidates, transform=None, coerce_numeric=False):
    """Return first available field from `candidates` in the row, optionally transformed."""
    if row is None:
        return None
    for c in candidates:
        if c in row.index:
            val = row[c]
            if coerce_numeric:
                import pandas as pd
                val = pd.to_numeric([val], errors="coerce")[0]
            if transform:
                try:
                    val = transform(val)
                except Exception:
                    pass
            return val
    return None


def calculate_duration(stryd_df):

    if 'Local Timestamp' not in stryd_df.columns:
        raise ValueError("DataFrame must contain a 'Local Timestamp' column.")

    start_time = stryd_df['Local Timestamp'].iloc[0]
    end_time = stryd_df['Local Timestamp'].iloc[-1]

    duration = end_time - start_time

    # Format duration as string (without days, if present)
    duration_str = str(duration)
    if "day" in duration_str:
        duration_str = str(timedelta(seconds=duration.total_seconds() % 86400))  # 86400 = seconds in a day

    # Store formatted duration in the DataFrame
    stryd_df['run_duration'] = duration_str

    return stryd_df, duration, duration_str