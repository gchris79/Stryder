import logging
from zoneinfo import available_timezones

from db_schema import insert_workout, insert_run, insert_metrics, get_or_create_workout_type
from file_parsing import normalize_workout_type, load_csv, edit_stryd_csv, match_workout_name, calculate_duration


def insert_full_run(stryd_df, workout_name, notes, avg_hr, conn):

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


def prompt_for_timezone():
    valid_timezones = set(available_timezones())

    while True:
        tz_input = input("🌍 Enter the timezone of the Garmin activity (e.g., Europe/Athens): ").strip()
        if tz_input in valid_timezones:
            return tz_input
        else:
            print("❌ Invalid timezone. Try again or type 'list' to see options.")
            if tz_input.lower() == "list":
                for tz in sorted(valid_timezones):
                    print(" -", tz)


def process_csv_pipeline(stryd_csv_path, garmin_csv_path):
    # Step 1: Load both CSVs
    stryd_df, garmin_df = load_csv(stryd_csv_path, garmin_csv_path)

    # Step 2: Clean, convert, and calculate
    stryd_df = edit_stryd_csv(stryd_df)

    garmin_tz_str = prompt_for_timezone()
    stryd_df = match_workout_name(stryd_df, garmin_df, garmin_tz_str)
    stryd_df, duration_td, duration_str = calculate_duration(stryd_df)

    return stryd_df, duration_td, duration_str

