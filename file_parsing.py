import logging
import pandas as pd
from datetime import timedelta
from zoneinfo import ZoneInfo
import tzlocal


def load_csv(stryd_csv, garmin_csv):
    stryd_df = pd.read_csv(stryd_csv)
    garmin_df = pd.read_csv(garmin_csv)
    return stryd_df, garmin_df


def edit_stryd_csv(df):
    df['UTC Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s', utc=True)
    local_tz = ZoneInfo(tzlocal.get_localzone_name())
    df['Local Timestamp'] = df['UTC Timestamp'].dt.tz_convert(local_tz)

    cols = ['Local Timestamp', 'UTC Timestamp'] + [
        col for col in df.columns if col not in ['Local Timestamp', 'UTC Timestamp']
    ]
    df = df[cols]

    df = df.sort_values('UTC Timestamp').reset_index(drop=True)
    df['Time Delta'] = df['UTC Timestamp'].diff().dt.total_seconds().fillna(0)
    df['Distance Delta'] = df['Stryd Speed (m/s)'] * df['Time Delta']
    df['Stryd Distance (meters)'] = df['Distance Delta'].cumsum()

    return df


def normalize_workout_type(raw_name):
    name = raw_name.lower()
    if "ez" in name or "easy" in name:
        return "Easy Run"
    elif "long" in name:
        return "Long Run"
    elif "threshold" or "intervals" in name:
        return "Threshold"
    elif  "test" or "testing" or "trial" or "tt" in name:
        return "Testing"
    elif "race" in name:
        return "Race"
    else:
        return "Other"


def match_workout_name(stryd_df, garmin_df, garmin_timezone_str):
    stryd_start_time = stryd_df.loc[0, 'UTC Timestamp']
    garmin_df.columns = garmin_df.columns.str.strip()

    if not pd.api.types.is_datetime64_any_dtype(garmin_df['Date']):
        garmin_df['Date'] = pd.to_datetime(garmin_df['Date'], format='%Y-%m-%d %H:%M:%S')

    garmin_df['Date'] = garmin_df['Date'].dt.tz_localize(ZoneInfo(garmin_timezone_str)).dt.tz_convert('UTC')

    tolerance = timedelta(seconds=60)
    matched_title = None

    for row in garmin_df.itertuples(index=False):
        garmin_time = row.Date
        delta = abs(garmin_time - stryd_start_time)
        logging.debug(f"Comparing Stryd UTC: {stryd_start_time} vs Garmin UTC: {garmin_time} → Δ {delta}")

        if delta <= tolerance:
            matched_title = row.Title
            logging.info(f"✅ Match found: '{matched_title}' at {garmin_time}")
            break

    if matched_title:
        stryd_df['Workout Name'] = matched_title
        stryd_df.to_csv("stryd_matched_with_workout.csv", index=False)
    else:
        logging.warning("❌ No Garmin match found within tolerance.")
        stryd_df['Workout Name'] = "Unknown"

    return stryd_df


def calculate_duration(stryd_df):
    if 'Local Timestamp' not in stryd_df.columns:
        raise ValueError("DataFrame must contain a 'Local Timestamp' column.")

    start_time = stryd_df['Local Timestamp'].iloc[0]
    end_time = stryd_df['Local Timestamp'].iloc[-1]
    duration = end_time - start_time

    duration_str = str(duration)
    if "day" in duration_str:
        duration_str = str(timedelta(seconds=duration.total_seconds() % 86400))

    stryd_df['run_duration'] = duration_str
    return stryd_df, duration, duration_str
