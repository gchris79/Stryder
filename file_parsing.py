import logging
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import tzlocal

def load_csv(stryd_csv, garmin_csv):
    stryd_df = pd.read_csv(stryd_csv)
    garmin_df = pd.read_csv(garmin_csv)
    return stryd_df, garmin_df

def edit_stryd_csv(df):
    # Convert Unix timestamps to local time
    df['Local Timestamp'] = pd.to_datetime(
        df['Timestamp'], unit='s', utc=True
    ).dt.tz_convert(ZoneInfo(tzlocal.get_localzone_name()))

    # Move the Local Timestamp to the first column
    cols = ['Local Timestamp'] + [col for col in df.columns if col != 'Local Timestamp']
    df = df[cols]

     # Calculates Stryd Distance from Stryd Speed
    df = df.sort_values('Local Timestamp').reset_index(drop=True)
    df['Time Delta'] = df['Local Timestamp'].diff().dt.total_seconds().fillna(0)
    df['Distance Delta'] = df['Stryd Speed (m/s)'] * df['Time Delta']
    df['Stryd Distance (meters)'] = df['Distance Delta'].cumsum()

    return df


def normalize_workout_type(raw_name):
    name = raw_name.lower()
    if "ez" in name or "easy" in name:
        return "Easy Run"
    elif "long" in name:
        return "Long Run"
    elif "threshold" in name:
        return "Threshold"
    elif "vo2" in name:
        return "VO2 Max"
    elif "race" in name:
        return "Race"
    else:
        return "Other"


def match_workout_name(stryd_df, garmin_df):
    local_tz = ZoneInfo(tzlocal.get_localzone_name())

    stryd_start_time = stryd_df.loc[0, 'Local Timestamp']

    garmin_df.columns = garmin_df.columns.str.strip()

    if not pd.api.types.is_datetime64_any_dtype(garmin_df['Date']):
        garmin_df['Date'] = pd.to_datetime(garmin_df['Date'], format='%Y-%m-%d %H:%M:%S')

    if garmin_df['Date'].dt.tz is None:
        garmin_df['Date'] = garmin_df['Date'].dt.tz_localize(local_tz, ambiguous='NaT').dt.tz_convert('UTC')

    if stryd_start_time.tzinfo is None:
        stryd_start_time = stryd_start_time.replace(tzinfo=ZoneInfo("UTC"))
    else:
        stryd_start_time = stryd_start_time.astimezone(ZoneInfo("UTC"))

    tolerance = timedelta(seconds=60)
    matched_title = None

    for row in garmin_df.itertuples(index=False):
        garmin_time = row.Date

        delta = abs(garmin_time - stryd_start_time)
        logging.debug(f"Comparing Stryd: {stryd_start_time} vs Garmin: {garmin_time} → Δ {delta}")

        if delta <= tolerance:
            matched_title = row.Title
            logging.info(f"✅ Match found: '{matched_title}' at {garmin_time}")
            break

    if matched_title:
        stryd_df['Workout Name'] = matched_title
        stryd_df.to_csv("stryd_matched_with_workout.csv", index=False)
        return stryd_df
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

    # Format duration as string (without days, if present)
    duration_str = str(duration)
    if "day" in duration_str:
        duration_str = str(timedelta(seconds=duration.total_seconds() % 86400))  # 86400 = seconds in a day

    # Store formatted duration in the DataFrame
    stryd_df['run_duration'] = duration_str

    return stryd_df, duration, duration_str