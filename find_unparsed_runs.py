import sqlite3
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
import tzlocal

from config import DB_PATH, STRYD_FOLDER, GARMIN_CSV_PATH
from pipeline import process_csv_pipeline, insert_full_run
from db_schema import run_exists

def get_existing_datetimes(conn):
    cur = conn.cursor()
    cur.execute("SELECT datetime FROM runs")
    return {row[0] for row in cur.fetchall()}


def convert_first_timestamp_to_str(file_path, tz):
    df = pd.read_csv(file_path)
    if 'Timestamp' not in df.columns or df['Timestamp'].empty:
        raise ValueError("Missing or empty 'Timestamp' column")

    ts = pd.to_datetime(df['Timestamp'].iloc[0], unit='s', utc=True)
    local_ts = ts.tz_convert(tz)
    return local_ts.isoformat(sep=' ', timespec='seconds')


def main():
    local_tz = ZoneInfo(tzlocal.get_localzone_name())
    folder = Path(STRYD_FOLDER)

    conn = sqlite3.connect(DB_PATH)
    existing_times = get_existing_datetimes(conn)

    unparsed = []
    total_files = 0

    for file in folder.glob("*.csv"):
        total_files += 1
        try:
            ts_str = convert_first_timestamp_to_str(file, local_tz)
            if ts_str not in existing_times:
                unparsed.append(file.name)
        except Exception as e:
            print(f"❌ Failed to check {file.name}: {e}")
            unparsed.append(file.name)

    print(f"\n✅ Total STRYD files found: {total_files}")
    print(f"✅ Parsed files in DB: {total_files - len(unparsed)}")
    print(f"❗ Unparsed files: {len(unparsed)}")

    if unparsed:
        print("\n📂 Missing/Skipped files:")
        for name in unparsed:
            print(" -", name)

        for name in unparsed:
            file_path = folder / name
            print(f"\n🔍 File: {name}")
            choice = input("⚙️  Do you want to parse this run? [y/N]: ").strip().lower()

            if choice.lower() != 'y':
                print("⏭️  Skipping.")
                continue

            try:
                stryd_df, duration_td, duration_str = process_csv_pipeline(str(file_path), GARMIN_CSV_PATH)

                start_time_str = stryd_df['Local Timestamp'].iloc[0].isoformat(sep=' ', timespec='seconds')
                if run_exists(conn, start_time_str):
                    print(f"⚠️  Run at {start_time_str} already exists. Skipping.")
                    continue

                workout_name = stryd_df["Workout Name"].iloc[0] if "Workout Name" in stryd_df else "Unknown"
                notes = ""
                avg_hr = None

                insert_full_run(stryd_df, workout_name, notes, avg_hr, conn)
                print(f"✅ Inserted: {name}")

            except Exception as e:
                print(f"❌ Failed to process {name}: {e}")

if __name__ == "__main__":
    main()
