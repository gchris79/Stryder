# batch_import.py (updated with timezone prompting and mismatch correction logic)

import logging
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo, available_timezones
import pandas as pd

from pipeline import insert_full_run, process_csv_pipeline
from db_schema import run_exists
from file_parsing import load_csv, edit_stryd_csv, match_workout_name, calculate_duration


def suggest_timezones_for_offset(offset_hours):
    suggestions = []
    for tz in sorted(available_timezones()):
        try:
            zone = ZoneInfo(tz)
            now = timedelta(hours=offset_hours)
            if zone.utcoffset(None) == timedelta(hours=offset_hours):
                suggestions.append(tz)
        except Exception:
            continue
    return suggestions


def format_timedelta_clean(delta):
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}"


def batch_process_stryd_folder(stryd_folder, garmin_csv_path, conn):
    stryd_files = list(Path(stryd_folder).glob("*.csv"))
    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")

    # Prompt once for the initial Garmin timezone
    current_garmin_tz = prompt_for_timezone()

    for file in stryd_files:
        logging.info(f"\n🔄 Processing {file.name}")
        try:
            # Load and convert
            stryd_df, garmin_df = load_csv(str(file), garmin_csv_path)
            stryd_df = edit_stryd_csv(stryd_df)

            # Try matching
            stryd_start_utc = stryd_df.loc[0, "UTC Timestamp"]
            garmin_df_converted = garmin_df.copy()
            matched_df = match_workout_name(stryd_df.copy(), garmin_df_converted, current_garmin_tz)

            if matched_df["Workout Name"].iloc[0] == "Unknown":
                garmin_df['Parsed Date'] = pd.to_datetime(garmin_df['Date'], format='%Y-%m-%d %H:%M:%S')
                garmin_df['UTC Guess'] = garmin_df['Parsed Date'].dt.tz_localize(ZoneInfo(current_garmin_tz)).dt.tz_convert('UTC')
                closest_row = garmin_df.loc[(garmin_df['UTC Guess'] - stryd_start_utc).abs().idxmin()]
                garmin_utc_guess = closest_row['UTC Guess']
                delta = stryd_start_utc - garmin_utc_guess

                logging.warning(f"❌ Match failed for {file.name}")
                logging.info(f"Stryd UTC start: {stryd_start_utc}")
                logging.info(f"Garmin UTC (as {current_garmin_tz}): {garmin_utc_guess}")
                logging.info(f"Difference: {format_timedelta_clean(delta)}")

                if abs(delta.total_seconds()) >= 60:
                    offset_hours = round(delta.total_seconds() / 3600)
                    candidates = suggest_timezones_for_offset(offset_hours)
                    logging.info(f"🔍 Suggested timezones for offset {offset_hours:+}:\n  - " + "\n  - ".join(candidates[:5]))

                    new_tz = input(f"Enter a new timezone (or press Enter to keep {current_garmin_tz}): ").strip()
                    if new_tz in available_timezones():
                        current_garmin_tz = new_tz
                        matched_df = match_workout_name(stryd_df.copy(), garmin_df, current_garmin_tz)
                    elif new_tz:
                        print("❌ Invalid timezone. Skipping run.")
                        continue

            # If still unmatched, skip the file
            if matched_df["Workout Name"].iloc[0] == "Unknown":
                logging.warning(f"⚠️ Skipping {file.name} — could not match with Garmin.")
                continue

            stryd_df = matched_df
            stryd_df, duration_td, duration_str = calculate_duration(stryd_df)

            start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
            if run_exists(conn, start_time_str):
                logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                continue

            workout_name = stryd_df["Workout Name"].iloc[0] if "Workout Name" in stryd_df else "Unknown"
            notes = ""
            avg_hr = None

            insert_full_run(stryd_df, workout_name, notes, avg_hr, conn)
            logging.info(f"✅ Inserted: {file.name}")

        except Exception as e:
            logging.error(f"❌ Failed to process {file.name}: {e}")


def prompt_for_timezone():
    valid_timezones = set(available_timezones())
    while True:
        tz_input = input("🌍 Enter the timezone of the Garmin activities (e.g., Europe/Athens): ").strip()
        if tz_input in valid_timezones:
            return tz_input
        elif tz_input.lower() == "list":
            print("\nAll timezones:")
            for tz in sorted(valid_timezones):
                print(" -", tz)
        else:
            print("❌ Invalid timezone. Try again or type 'list' to view options.")
