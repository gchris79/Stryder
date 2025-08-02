import logging
from pathlib import Path
import sqlite3
from pipeline import insert_full_run, process_csv_pipeline
from db_schema import run_exists



def batch_process_stryd_folder(stryd_folder: Path, garmin_csv_path, conn, timezone_str):
    parsed_files = []
    skipped_files = []

    stryd_files = list(Path(stryd_folder).glob("*.csv"))
    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")
    logging.debug(f"Connection object: {conn}")
    for file in stryd_files:
        logging.info(f"\n🔄 Processing {file.name}")
        try:
            # Step 1: Process file
            stryd_df, duration_td, duration_str, workout_name = process_csv_pipeline(str(file), garmin_csv_path, timezone_str)




            # Step 2: Skip if no Garmin match
            if stryd_df["Workout Name"].iloc[0] == "Unknown":
                logging.warning("⚠️  Skipping unmatched run (check unparsed files).")
                skipped_files.append(file.name)
                continue

            # Step 3: Check if already in DB
            start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
            if run_exists(conn, start_time_str):
                logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                continue

            # Step 4: Insert to DB
            workout_name = stryd_df["Workout Name"].iloc[0]
            notes = ""
            avg_hr = None
            insert_full_run(stryd_df, workout_name, notes, avg_hr, conn)
            parsed_files.append(file.name)
            logging.info(f"✅ Inserted: {file.name}")


        except sqlite3.ProgrammingError as e:
            if "closed" in str(e):
                logging.critical(f"❌ Database was closed before processing {file.name}. Aborting batch.")
                break  # or return, or re-open DB and continue — your choice
            else:
                logging.error(f"❌ SQLite error while processing {file.name}: {e}")
        except Exception as e:
            logging.error(f"❌ Failed to process {file.name}: {e}")

    # Final summary
    print("\n📊 Batch Summary:")
    print(f"✅ Parsed: {len(parsed_files)}")
    print(f"❌ Skipped: {len(skipped_files)}")

    if skipped_files:
        print("🗂 Skipped files:")
        for name in skipped_files:
            print(f" - {name}")
