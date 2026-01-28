import logging
from pathlib import Path
from typing import Callable

import pandas as pd
from stryder_core.pipeline import insert_full_run, process_csv_pipeline
from stryder_core.file_parsing import ZeroStrydDataError
from stryder_core.db_schema import run_exists
from stryder_core.utils import loadcsv_2df


def batch_process_stryd_folder(
        stryd_folder, garmin_csv_path, conn,
        timezone_str: str | None = None,
        on_progress: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ):
    """Creates raw df's from Stryd/Garmin files, normalizes them via pipeline,
    checks if run already exists -> skip parsing, if not inserts the run.
    Logs per-file details and returns a summary dict.
    """
    stryd_files = list(Path(stryd_folder).glob("*.csv"))
    logging.info(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")
    if on_progress:
        on_progress(f"📦 Found {len(stryd_files)} Stryd CSVs to process.")

    parsed = skipped = 0

    garmin_raw_df = loadcsv_2df(garmin_csv_path)

    canceled = False

    for file in stryd_files:
        # Check if user canceled parsing before finishing all the files
        if should_cancel and should_cancel():
            canceled = True
            break

        logging.info(f"\n🔄 Processing {file.name}")
        if on_progress:
            on_progress(f"🔄 Processing {file.name}")

        stryd_raw_df = loadcsv_2df(file)

        run_result = evaluate_run_from_dfs(
            stryd_raw_df,
            garmin_raw_df,
            file.name,
            conn,
            timezone_str,
            on_progress=on_progress
        )
        if run_result["status"] == "ok":
            insert_full_run(
                run_result["stryd_df"],
                run_result["workout_name"],
                notes="",
                avg_power=run_result["avg_power"],
                avg_hr=run_result["avg_hr"],
                total_m=run_result["total_m"],
                conn=conn,
            )
            parsed += 1

        else:
            skipped += 1

    logging.info(
        "Batch completed: %d parsed, %d skipped (total %d files)",
        parsed, skipped, len(stryd_files),
    )
    if on_progress:
        on_progress(f"Batch completed: {parsed}, {skipped} (total {len(stryd_files)})")

    # Structured return for the UI
    return {
        "mode": "batch",
        "parsed": parsed,
        "skipped": skipped,
        "files_total": len(stryd_files),
        "canceled" : canceled
    }


def single_process_stryd_file(stryd_csv_path, garmin_csv_path, conn, timezone_str: str | None = None):
    """
    Core engine for importing a single Stryd file.
    No prompts, no prints. Returns a status dict.
    """
    stryd_file = Path(stryd_csv_path)
    garmin_file = Path(garmin_csv_path)

    if not stryd_file.exists():
        logging.warning(f"Stryd CSV not found: {stryd_file}")
        return {"status": "file_not_found"}

    if not garmin_file.exists():
        logging.error(f"Garmin CSV not found: {garmin_file}")
        return {"status": "garmin_not_found"}

    result = prepare_run_insert(stryd_file, garmin_file, stryd_file.name, conn, timezone_str)
    return {
        "status": result["status"],
        "file": stryd_file,
        "start_time": result["start_time"],
        "avg_power": result["avg_power"],
        "avg_hr": result["avg_hr"],
        "total_m": result["total_m"],
        "error": result["error"],
        "workout_name": result["workout_name"],
        "stryd_df": result["stryd_df"],
    }



def prepare_run_insert(stryd_file, garmin_file, file_name, conn, timezone_str):
    """ Checks the run if it can be parsed or not and return a dict with info about it. Works in two steps
        a) Creates the dataframes of Stryd and Garmin files
        b) calls evaluate_run_from_dfs to evaluate and return a dictionary for output in the UI """
    # Transform Stryd and Garmin csv's to dataframes
    stryd_raw_df = loadcsv_2df(stryd_file)
    garmin_raw_df = loadcsv_2df(garmin_file)
    return evaluate_run_from_dfs(stryd_raw_df, garmin_raw_df, file_name, conn, timezone_str)


def evaluate_run_from_dfs(stryd_raw_df, garmin_raw_df, file_name, conn, timezone_str,
                          on_progress: Callable[[str], None] | None = None):
    """
    Core logic: takes *already loaded* raw dataframes,
    runs the pipeline, checks DB, and returns the result dict.
    No CSV loading at all.
    """


    result = {
        "status": "error",  # default value
        "workout_name": None,
        "start_time": None,
        "avg_power": None,
        "avg_hr": None,
        "total_m": None,
        "stryd_df": None,
        "error": None,
    }
    try:
        stryd_df, _, avg_power, _, avg_hr, total_m = process_csv_pipeline(stryd_raw_df, garmin_raw_df, timezone_str,
                                                                          file_name)
        result["avg_power"] = avg_power
        result["avg_hr"] = avg_hr
        result["total_m"] = total_m
        result["stryd_df"] = stryd_df
        # ✅ Use LOCAL timestamp string to match DB, no UTC conversion here
        start_time = stryd_df["ts_local"].iloc[0]
        start_time_str = start_time.isoformat(sep=' ', timespec='seconds')
        result["start_time"] = start_time_str

        # Check the DB to avoid re-inserts
        if run_exists(conn, start_time_str):
            logging.info(f"⚠️  Run already exists in DB: {file_name} ({start_time_str})")
            if on_progress:
                on_progress(f"⚠️  Run already exists in DB: {file_name} ({start_time_str})")
            result["status"] = "already_exists"
            return result

    except ZeroStrydDataError as e:
        logging.info(f"⏭️ Run skipped due to zero Stryd speed/distance: {file_name} — {e}")
        if on_progress:
            on_progress(f"⏭️ Run skipped due to zero Stryd speed/distance: {file_name} — {e}")
        result["status"] = "zero_data"
        return result

    except Exception as e:
        logging.error(f"❌ Failed to process {file_name}: {e}")
        if on_progress:
            on_progress(f"❌ Failed to process {file_name}: {e}")
        result["error"] = str(e)
        result["status"] = "error"
        return result

    workout_name = stryd_df.get("wt_name", pd.Series(["Unknown"])).iloc[0]

    # Garmin matched
    result["workout_name"] = workout_name
    if workout_name != "Unknown":
        logging.info(f"✅ Garmin match found: {file_name} - {total_m / 1000:.2f} km")
        if on_progress:
            on_progress(f"✅ Garmin match found: {file_name} - {total_m / 1000:.2f} km")
        result["status"] = "ok"
        return result

    else:
        logging.info(f"✅ No Garmin match found: {file_name}")
        if on_progress:
            on_progress(f"✅ No Garmin match found: {file_name}")
        result["status"] = "no_garmin"
        return result