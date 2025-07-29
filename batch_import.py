import logging
from pathlib import Path

from pipeline import insert_full_run, process_csv_pipeline
from schema_db import run_exists



def batch_process_stryd_folder(stryd_folder, garmin_csv_path, conn):
    stryd_files = list(Path(stryd_folder).glob("*.csv"))

    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")

    for file in stryd_files:
        logging.info(f"\n🔄 Processing {file.name}")
        try:
            # Process using the full pipeline
            stryd_df, duration_td, duration_str = process_csv_pipeline(str(file), garmin_csv_path)

            # Check if this run is already in DB
            start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
            if run_exists(conn, start_time_str):
                logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                continue

            # Define BEFORE use
            workout_name = stryd_df["Workout Name"].iloc[0] if "Workout Name" in stryd_df else "Unknown"
            notes = ""
            avg_hr = None

            # Insert to DB
            insert_full_run(stryd_df, workout_name, notes, avg_hr, conn)
            logging.info(f"✅ Inserted: {file.name}")

        except Exception as e:
            logging.error(f"❌ Failed to process {file.name}: {e}")