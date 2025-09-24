import logging
from pathlib import Path
import pandas as pd
from pipeline import insert_full_run, process_csv_pipeline
from db_schema import run_exists
from file_parsing import ZeroStrydDataError


def batch_process_stryd_folder(stryd_folder, garmin_csv_path, conn, timezone_str: str | None = None):

    stryd_files = list(Path(stryd_folder).glob("*.csv"))
    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")

    parsed = skipped = 0

    for file in stryd_files:
        logging.info(f"\n🔄 Processing {file.name}")
        try:
            stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m = process_csv_pipeline(
                str(file), garmin_csv_path, timezone_str=timezone_str
            )

            start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
            if run_exists(conn, start_time_str):
                logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                skipped += 1
                continue

            workout_name = stryd_df.get("Workout Name", pd.Series(["Unknown"])).iloc[0]
            if workout_name == "Unknown":
                logging.info(f"⏭️  Skipped {file.name} (no Garmin match within tolerance).")
                skipped += 1
                continue

            insert_full_run(stryd_df, workout_name, "",avg_power, avg_hr, total_m, conn)
            logging.info(f"✅ Inserted: {file.name} - Avg. Power: {avg_power} - Avg.HR: {avg_hr} - Distance: {total_m/1000:.2f} km")
            parsed += 1

        except ZeroStrydDataError as e:
            logging.warning(f"⏭️  Skipped {file.name}: {e}")
            skipped += 1

        except Exception as e:
            logging.error(f"❌ Failed to process {file.name}: {e}")
            skipped += 1

    logging.info("\n📊 Batch Summary:")
    logging.info(f"✅ Parsed: {parsed}")
    logging.info(f"⏭️ Skipped: {skipped}")
