import logging

from pathlib import Path
from db_schema import insert_workout, insert_run, insert_metrics, get_or_create_workout_type #run_exists
from file_parsing import normalize_workout_type, load_csv, edit_stryd_csv, match_workout_name, calculate_duration


def insert_full_run(stryd_df, workout_name, notes, avg_hr, conn):
    if conn is None:
        raise ValueError("❌ Cannot insert run — connection is None")
    # 1. Insert the workout
    # Get the normalized workout type (e.g., "Easy Run", "VO2 Max")
    workout_type = normalize_workout_type(workout_name)
    # Insert or fetch the workout type ID
    workout_type_id = get_or_create_workout_type(workout_type, conn)
    # Insert workout entry
    workout_id = insert_workout(workout_name, notes, workout_type_id, conn)

    # 2. Insert the run
    start_time = stryd_df["Local Timestamp"].iloc[0]
    end_time = stryd_df["Local Timestamp"].iloc[-1]
    duration_sec = int((end_time - start_time).total_seconds())
    # Insert run
    run_id = insert_run(workout_id, start_time, duration_sec, avg_hr, conn)

    # 3. Insert all second-by-second metrics
    insert_metrics(run_id, stryd_df, conn)

    logging.info(f"✅ Run saved: Workout ID {workout_id}, Run ID {run_id}")
    return workout_id, run_id


def process_csv_pipeline(stryd_csv_path, garmin_csv_path, timezone_str):
    raw_file = Path(stryd_csv_path).name
    # Step 1: Load both CSVs
    stryd_df, garmin_df = load_csv(stryd_csv_path, garmin_csv_path)
    logging.debug(f"📄 [{raw_file}] Loaded STRYD rows: {len(stryd_df)}")

    # Log raw Unix timestamp from file
    try:
        logging.debug(f"📄 [{raw_file}] First raw 'Timestamp': {stryd_df['Timestamp'].iloc[0]}")
    except Exception as e:
        logging.error(f"❌ [{raw_file}] Failed to read 'Timestamp': {e}")


    # Step 2: Clean, convert, and calculate
    stryd_df = edit_stryd_csv(stryd_df, timezone_str)
    logging.debug(f"🕒 [{raw_file}] Local TS: {stryd_df['Local Timestamp'].iloc[0]}")

    stryd_df, avg_HR = match_workout_name(stryd_df, garmin_df, timezone_str)
    workout_name = stryd_df['Workout Name'].iloc[0]
    logging.INFO(f"🏷️ [{raw_file}] Matched workout name: {workout_name}")


    stryd_df, duration_td, duration_str = calculate_duration(stryd_df)
    logging.INFO(f"⏱ [{raw_file}] Duration: {duration_str}")

    return stryd_df, duration_td, duration_str, workout_name, avg_HR



