import logging
import pandas as pd
from stryder_core.db_schema import insert_workout, insert_run, insert_metrics, get_or_create_workout_type
from stryder_core.file_parsing import (normalize_workout_type, edit_stryd_csv, calculate_duration,
                                       get_matched_garmin_row, is_stryd_all_zero, ZeroStrydDataError)


def insert_full_run(stryd_df, workout_name, notes, avg_power, avg_hr, total_m,  conn):
    """ Takes Stryd df creates workout type from workout name, calculates duration,
        takes run_id and inserts all the metrics, returns workout_id and run_id"""
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
    start_time = stryd_df["ts_local"].iloc[0]
    end_time = stryd_df["ts_local"].iloc[-1]
    duration_sec = int((end_time - start_time).total_seconds())

    # Insert run
    run_id = insert_run(workout_id, start_time, avg_power, duration_sec, avg_hr, total_m, conn)

    # 3. Insert all second-by-second metrics
    insert_metrics(run_id, stryd_df, conn)

    logging.info(f"✅ Run saved: Workout ID {workout_id}, Run ID {run_id}")
    return workout_id, run_id


def process_csv_pipeline(stryd_df, garmin_df, timezone_str=None, stryd_label: str | None = None):
    """ Takes Stryd and Garmin dataframes matches them, returns canonical Stryd df, plus duration, distance, average power and HR """
    logging.debug(f"📄 [{stryd_label}] Loaded STRYD rows: {len(stryd_df)}")

    # Clean, convert, and calculate, stryd_df gets canonical column names
    stryd_df = edit_stryd_csv(stryd_df, timezone_str=timezone_str)

    if is_stryd_all_zero(stryd_df):
        raise ZeroStrydDataError("Stryd speed/distance is all zeros — skipping.")

    # Find matched Garmin row once
    matched = get_matched_garmin_row(stryd_df, garmin_df, timezone_str=timezone_str, tolerance_sec=60)

    # Match workout name from Garmin and pass it to Stryd workout name
    if matched is not None and "wt_name" in matched.index:
        stryd_df["wt_name"] = matched["wt_name"]
        logging.info(f"✅ Match found: '{matched['wt_name']}' at {matched['date']}")
    else:
        stryd_df["wt_name"] = "Unknown"
        logging.info("❌ No Garmin match found within tolerance.")

    # Calculate duration
    stryd_df, duration_td, duration_str = calculate_duration(stryd_df)
    logging.info(f"⏱ [{stryd_label}] Duration: {duration_str}")

    # Calculate distance (meters)
    total_m = float(stryd_df["str_dist_m"].iloc[-1]) if "str_dist_m" in stryd_df.columns else 0.0

    # Calculate power
    avg_power = float(stryd_df["power_sec"].mean()) if "power_sec" in stryd_df.columns else 0.0

    # Generate Avg HR from Garmin df
    if matched is not None and "avg_hr" in matched.index:
        val = matched["avg_hr"]
        avg_hr = int(round(val)) if pd.notna(val) else None
    else:
        avg_hr = None

    return stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m