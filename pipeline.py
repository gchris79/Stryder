import logging
from pathlib import Path
import pandas as pd
from db_schema import insert_workout, insert_run, insert_metrics, get_or_create_workout_type
from file_parsing import (normalize_workout_type, load_csv, edit_stryd_csv, calculate_duration,
                          get_matched_garmin_row, garmin_field, _is_stryd_all_zero,
                          ZeroStrydDataError)


def insert_full_run(stryd_df, workout_name, notes, avg_power, avg_hr, total_m,  conn):
    if conn is None:
        raise ValueError("❌ Cannot insert run — connection is None")
    # 1. Insert the workout
    # Get the normalized workout type (e.g., "Easy Run", "VO2 Max")
    workout_type = normalize_workout_type(workout_name)
    # Insert or fetch the workout type ID
    workout_type_id = get_or_create_workout_type(workout_type, conn)
    # Insert workout entry
    workout_id = insert_workout(workout_name, notes, workout_type_id, conn)

    # 2. Calculate duration
    start_time = stryd_df["Local Timestamp"].iloc[0]
    end_time = stryd_df["Local Timestamp"].iloc[-1]
    duration_sec = int((end_time - start_time).total_seconds())

    # Insert run
    run_id = insert_run(workout_id, start_time, avg_power, duration_sec, avg_hr, total_m, conn)

    # 3. Insert all second-by-second metrics
    insert_metrics(run_id, stryd_df, conn)

    logging.info(f"✅ Run saved: Workout ID {workout_id}, Run ID {run_id}")
    return workout_id, run_id


def process_csv_pipeline(stryd_csv_path, garmin_csv_path, timezone_str=None):

    raw_file = Path(stryd_csv_path).name

    # Load both files
    stryd_df, garmin_df = load_csv(stryd_csv_path, garmin_csv_path)
    logging.debug(f"📄 [{raw_file}] Loaded STRYD rows: {len(stryd_df)}")

    # Clean, convert, and calculate
    stryd_df = edit_stryd_csv(stryd_df, timezone_str=timezone_str)

    if _is_stryd_all_zero(stryd_df):
        raise ZeroStrydDataError("Stryd speed/distance is all zeros — skipping.")

    # Find matched Garmin row once
    matched = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=timezone_str, tolerance_sec=60)

    # Match name from Garmin if with Stryd workout name
    if matched is not None and "Title" in matched.index:
        stryd_df["Workout Name"] = matched["Title"]
        logging.info(f"✅ Match found: '{matched['Title']}' at {matched['Date']}")
    else:
        stryd_df["Workout Name"] = "Unknown"
        logging.info("❌ No Garmin match found within tolerance.")


    # Calculate duration
    stryd_df, duration_td, duration_str = calculate_duration(stryd_df)
    logging.info(f"⏱ [{raw_file}] Duration: {duration_str}")

    # Calculate distance (meters)
    total_m = float(stryd_df["Stryd Distance (meters)"].iloc[-1]) if "Stryd Distance (meters)" in stryd_df.columns else 0.0

    # Calculate power
    avg_power = float(stryd_df["Power (w/kg)"].mean()) if "Power (w/kg)" in stryd_df.columns else 0.0

    # Generate AvgHR from Garmin
    avg_hr_candidates = ["Avg HR", "Average HR", "Average Heart Rate", "Avg. HR", "Avg HR (bpm)"]
    avg_hr_val = garmin_field(matched, avg_hr_candidates, coerce_numeric=True,
                              transform=lambda v: int(round(v)) if pd.notna(v) else None)
    avg_hr = avg_hr_val if avg_hr_val is not None else None

    return stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m