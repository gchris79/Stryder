import pandas as pd
import logging
from zoneinfo import ZoneInfo
from pathlib import Path

from path_memory import load_last_used_paths, save_last_used_paths
from pipeline import process_csv_pipeline, insert_full_run
from db_schema import run_exists


def prompt_yes_no(prompt_msg, default=True):
    # Prompt the user for a yes/no input. Returns True for yes, False for no.
    # Default determines what happens on empty input.
    while True:
        user_input = input(f"{prompt_msg} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        if not user_input:
            return default
        if user_input in ["y", "yes"]:
            return True
        if user_input in ["n", "no"]:
            return False
        print("⚠️ Invalid input. Please enter Y or N.")


def prompt_for_timezone(file_name=None):
    example = "e.g. Europe/Athens"
    file_msg = f" for {file_name}" if file_name else ""
    tz_str = input(f"🌍 Timezone ({example}){file_msg} (or 'exit' to quit): ").strip()

    if tz_str.lower() in {"exit", "quit", "q"}:
        return "EXIT"

    try:
        ZoneInfo(tz_str)
        return tz_str
    except Exception:
        print("❌ Invalid timezone. Skipping.")
        return None


def convert_first_timestamp_to_str(file_path, tz):
    """
        Extracts the first timestamp from a Stryd CSV file and returns it
        as a UTC ISO string (used for DB comparison).
        """
    df = pd.read_csv(file_path)

    if 'Timestamp' not in df.columns or df['Timestamp'].empty:
        raise ValueError("Missing or empty 'Timestamp' column")

    # Step 1: Convert from Unix to UTC
    ts = pd.to_datetime(df['Timestamp'].iloc[0], unit='s', utc=True)

    # Step 2: Convert to local time then to UTC again (to match DB insert logic)
    local_ts = ts.tz_convert(tz).astimezone(ZoneInfo("UTC"))

    # Step 3: Return as string
    return local_ts.isoformat(sep=' ', timespec='seconds')


def get_paths_with_prompt():
    from config import STRYD_FOLDER, GARMIN_CSV_FILE

    # Try to load last used paths
    last_stryd, last_garmin = load_last_used_paths()
    if last_stryd and last_garmin:
        print("\n🧠 Last used paths:")
        print(f"📁 STRYD folder:     {last_stryd}")
        print(f"📄 Garmin CSV file:  {last_garmin}")
        if prompt_yes_no("♻️  Reuse these paths?"):
            return last_stryd, last_garmin

    # Ask if user wants defaults
    print("\n🛠️ Current default paths from config.py:")
    print(f"📁 STRYD folder:     {STRYD_FOLDER}")
    print(f"📄 Garmin CSV file:  {GARMIN_CSV_FILE}")
    if prompt_yes_no("📁 Use default paths from config.py?"):
        stryd_path = STRYD_FOLDER
        garmin_file = GARMIN_CSV_FILE
        if not stryd_path.exists():
            print(f"📁 Default STRYD folder missing, creating: {stryd_path}")
            stryd_path.mkdir(parents=True, exist_ok=True)
        return stryd_path, garmin_file

    # Manual path input
    stryd_path = Path(input("📂 Enter path to STRYD folder: ").strip())
    if not stryd_path.exists():
        print(f"📁 STRYD folder not found, creating: {stryd_path}")
        stryd_path.mkdir(parents=True, exist_ok=True)

    # Prompt for Garmin file until found or exit
    while True:
        garmin_file = Path(input("📄 Enter path to Garmin CSV file: ").strip())
        if garmin_file.exists():
            save_last_used_paths(stryd_path, garmin_file)
            break
        if not prompt_yes_no("❌ Garmin file not found. Try again?"):
            logging.warning("Aborted: Garmin file not provided. Operation cancelled.")
            return None, None

    return stryd_path, garmin_file


def interactive_run_insert(stryd_file, garmin_file, conn):
    """
    Attempts to process and insert a single run with user guidance.
    Returns True if inserted, False if skipped, or None if exited.
    """
    while True:
        timezone_str = prompt_for_timezone(stryd_file.name)
        if timezone_str == "EXIT":
            logging.info("👋 User exited early.")
            return None

        try:
            stryd_df, _, _, workout_name,avg_hr = process_csv_pipeline(stryd_file, garmin_file, timezone_str)

            # Convert to UTC and generate DB timestamp key
            start_time = stryd_df["Local Timestamp"].iloc[0]
            if start_time.tzinfo is not None:
                start_time = start_time.astimezone(ZoneInfo("UTC"))
            else:
                start_time = start_time.replace(tzinfo=ZoneInfo("UTC"))
            start_time_str = start_time.isoformat(sep=' ', timespec='seconds')

            # Check the DB to avoid re-inserts
            if run_exists(conn, start_time_str):
                logging.info(f"⚠️ Already in DB: {stryd_file.name} ({start_time_str})")
                return False

        except Exception as e:
            logging.error(f"❌ Failed to process {stryd_file}: {e}")
            return False

        # Garmin matched
        if workout_name != "Unknown":
            insert_full_run(stryd_df, workout_name, notes="", avg_hr=avg_hr, conn=conn)
            logging.info(f"✅ Inserted with Garmin match: {stryd_file}")
            return True

        # Garmin not matched → show menu
        print(f"\n❌ No Garmin match found for {stryd_file.name}.")
        x = input(
            "What would you like to do?\n"
            "[1] Parse anyway without Garmin match\n"
            "[2] Try another timezone\n"
            "[3] Skip for now\n"
            "[4] Exit\n> "
        ).strip()

        if x == "1":
            insert_full_run(stryd_df, workout_name, notes="", avg_hr=None, conn=conn)
            logging.info(f"✅ Inserted without Garmin match: {stryd_file}")
            return True

        elif x == "2":
            continue  # try another timezone

        elif x == "3":
            logging.info(f"⏭️ Skipped: {stryd_file}")
            return False

        elif x == "4":
            logging.info("👋 Exiting early.")
            return None

        else:
            print("❓ Invalid choice. Try again.")
