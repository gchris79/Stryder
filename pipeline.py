import logging

from db_schema import insert_workout, insert_run, insert_metrics, get_or_create_workout_type, run_exists
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
    # Step 1: Load both CSVs
    stryd_df, garmin_df = load_csv(stryd_csv_path, garmin_csv_path)

    # Step 2: Clean, convert, and calculate
    stryd_df = edit_stryd_csv(stryd_df, timezone_str)
    stryd_df = match_workout_name(stryd_df, garmin_df, timezone_str)
    stryd_df, duration_td, duration_str = calculate_duration(stryd_df)

    # Step 3: Extract and normalize workout name
    workout_name = stryd_df["Workout Name"].iloc[0] if "Workout Name" in stryd_df else "Unknown"
    #workout_type = normalize_workout_type(workout_name)  # may not be needed here, but safe

    return stryd_df, duration_td, duration_str, workout_name



