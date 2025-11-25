import logging
import sqlite3
from pathlib import Path
import pandas as pd
from stryder_core.pipeline import insert_full_run, process_csv_pipeline
from stryder_core.file_parsing import ZeroStrydDataError
from stryder_core.config import DB_PATH
from stryder_core.db_schema import run_exists
from stryder_core.find_unparsed_runs import find_unparsed_files
from utils import loadcsv_2df, interactive_run_insert, get_paths_with_prompt


def batch_process_stryd_folder(stryd_folder, garmin_csv_path, conn, timezone_str: str | None = None):
    """Creates raw df's from Stryd/Garmin files, normalizes them via pipeline,
    checks if run already exists -> skip parsing, if not inserts the run.
    Logs per-file details and returns a summary dict.
    """
    stryd_files = list(Path(stryd_folder).glob("*.csv"))
    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")

    parsed = skipped = 0

    garmin_raw_df = loadcsv_2df(garmin_csv_path)

    for file in stryd_files:
        logging.info(f"\n🔄 Processing {file.name}")
        try:
            stryd_raw_df = loadcsv_2df(file)
            stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m = process_csv_pipeline(
                stryd_raw_df, garmin_raw_df, timezone_str=timezone_str, stryd_label=file.name
            )

            start_time_str = stryd_df['ts_local'].iloc[0].isoformat(sep=' ', timespec='seconds')
            if run_exists(conn, start_time_str):
                logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                skipped += 1
                continue

            workout_name = stryd_df.get("wt_name", pd.Series(["Unknown"])).iloc[0]
            if workout_name == "Unknown":
                logging.info(f"⏭️  Skipped {file.name} (no Garmin match within tolerance).")
                skipped += 1
                continue

            insert_full_run(stryd_df, workout_name, "", avg_power, avg_hr, total_m, conn)
            logging.info(
                f"✅ Inserted: {file.name} - Avg. Power: {avg_power} - "
                f"Avg.HR: {avg_hr} - Distance: {total_m/1000:.2f} km"
            )
            parsed += 1

        except ZeroStrydDataError as e:
            logging.warning(f"⏭️  Skipped {file.name}: {e}")
            skipped += 1

        except Exception as e:
            logging.error(f"❌ Failed to process {file.name}: {e}")
            skipped += 1

    logging.info(
        "Batch completed: %d parsed, %d skipped (total %d files)",
        parsed, skipped, len(stryd_files),
    )

    # 🔹 NEW: structured return for the UI
    return {
        "mode": "batch",
        "parsed": parsed,
        "skipped": skipped,
        "files_total": len(stryd_files),
    }


def single_process_stryd_file(stryd_csv_path, garmin_csv_path, conn, timezone_str: str | None = None):
    """
    Core engine for importing a single Stryd file.
    No prompts, no prints. Returns a status dict.
    """
    stryd_file = Path(stryd_csv_path)
    garmin_file = Path(garmin_csv_path)

    if not stryd_file.exists():
        logging.warning(f"File not found: {stryd_file}")
        return {
            "mode": "single",
            "status": "file_not_found",
            "file": stryd_file,
        }

    if not garmin_file.exists():
        logging.error(f"Garmin CSV not found: {garmin_file}")
        return {
            "mode": "single",
            "status": "garmin_not_found",
            "file": garmin_file,
        }

    try:
        stryd_raw_df = loadcsv_2df(stryd_file)
        garmin_raw_df = loadcsv_2df(garmin_file)

        stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m = process_csv_pipeline(
            stryd_raw_df, garmin_raw_df, timezone_str=timezone_str, stryd_label=stryd_file.name
        )

        start_time_str = stryd_df['ts_local'].iloc[0].isoformat(sep=' ', timespec='seconds')

        if run_exists(conn, start_time_str):
            logging.warning(f"Run at {start_time_str} already exists. Skipping.")
            return {
                "mode": "single",
                "status": "already_exists",
                "file": stryd_file,
                "start_time": start_time_str,
            }

        workout_name = (
            stryd_df["wt_name"].iloc[0]
            if "wt_name" in stryd_df.columns and len(stryd_df) > 0
            else "Unknown"
        )

        if workout_name == "Unknown":
            logging.info(f"No Garmin match for {stryd_file.name}. Skipping.")
            return {
                "mode": "single",
                "status": "skipped_no_garmin",
                "file": stryd_file,
            }

        insert_full_run(stryd_df, workout_name, "", avg_power, avg_hr, total_m, conn)

        summary = f"Avg Power {avg_power}, Avg HR {avg_hr}, {total_m/1000:.2f} km"

        logging.info(f"Inserted {stryd_file.name} — {summary}")

        return {
            "mode": "single",
            "status": "inserted",
            "file": stryd_file,
            "start_time": start_time_str,
            "summary": summary,
        }

    except ZeroStrydDataError as e:
        logging.info(f"Zero data for {stryd_file.name}: {e}")
        return {
            "mode": "single",
            "status": "zero_data",
            "file": stryd_file,
            "error": str(e),
        }

    except Exception as e:
        logging.error(f"Failed to import {stryd_file.name}: {e}")
        return {
            "mode": "single",
            "status": "error",
            "file": stryd_file,
            "error": str(e),
        }


def find_unparsed_cli():
    """ The CLI option for import unparsed runs"""

    timezone_str = input("🌍 Please, add a timezone for these runs (e.g. Europe/Athens): ").strip()

    stryd_folder, garmin_file = get_paths_with_prompt()

    conn = sqlite3.connect(DB_PATH)
    result = find_unparsed_files(stryd_folder, conn)

    total_files = result["total_files"]
    unparsed_files = result["unparsed_files"]
    parsed_files = result["parsed_files"]

    print(f"\n✅ Total STRYD files found: {total_files}")
    print(f"✅ Parsed files in DB: {parsed_files}")
    print(f"❗ Unparsed files: {len(unparsed_files)}")

    if not unparsed_files:
        print("\n🎉 Nothing to do. All files are already parsed.")
        return

    # Then run your interactive step:
    parsed_count = 0
    skipped_count = 0

    for file in unparsed_files:
        result = interactive_run_insert(str(file), garmin_file, conn, timezone_str)
        if result:
            parsed_count += 1
        elif result is False:
            skipped_count += 1
        elif result is None:
            print("\n🧾 Summary so far:")
            print(f"🔢 Total attempted: {parsed_count + skipped_count}")
            print(f"✅ Parsed: {parsed_count}")
            print(f"⏭️ Skipped: {skipped_count}")
            print(f"👋 Exited early before completing all {len(unparsed_files)} files.")
            conn.close()
            return

    print("\n🧾 Parsing complete.")
    print(f"🔢 Total unparsed files: {len(unparsed_files)}")
    print(f"✅ Parsed: {parsed_count}")
    print(f"⏭️ Skipped: {skipped_count}")

    conn.close()