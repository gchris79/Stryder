import sqlite3
import pandas as pd
from pathlib import Path
from utils import interactive_run_insert, get_paths_with_prompt
from date_utilities import resolve_tz
from config import DB_PATH


def get_existing_datetimes(conn):
    cur = conn.cursor()
    cur.execute("SELECT datetime FROM runs")
    return {row[0] for row in cur.fetchall()}


def convert_first_timestamp_to_str(file_path, _tz_ignored):
    df = pd.read_csv(file_path)
    if 'Timestamp' not in df.columns or df['Timestamp'].empty:
        raise ValueError("Missing or empty 'Timestamp' column")

    # Parse as UTC (tz-aware) and pick the earliest sample
    ts = pd.to_datetime(df['Timestamp'], unit='s', utc=True).min()

    # Store/compare in UTC to match how runs.datetime is saved in the DB
    return ts.isoformat(sep=' ', timespec='seconds')


def main():
    # # choose tz once; use same for all comparisons
    timezone_str = input("🌍 Please, add a timezone for these runs (e.g. Europe/Athens): ").strip()
    tz = resolve_tz(timezone_str)

    stry_folder, garmin_file = get_paths_with_prompt()
    conn = sqlite3.connect(DB_PATH)
    existing_times = get_existing_datetimes(conn)  # set of strings


    unparsed: list[Path] = []
    total_files = 0

    # Pass Path objects around; do not store strings
    for file in stry_folder.glob("*.csv"):
        total_files += 1
        try:
            ts_str = convert_first_timestamp_to_str(file, tz)
            if ts_str in existing_times:
                continue
            else:
                unparsed.append(file)   # only truly unparsed

        except Exception as e:
            print(f"❌ Failed to check {file.name}: {e}")
            # if unreadable, treat as unparsed so user can try interactively
            unparsed.append(file)

    print(f"\n✅ Total STRYD files found: {total_files}")
    print(f"✅ Parsed files in DB: {total_files - len(unparsed)}")
    print(f"❗ Unparsed files: {len(unparsed)}")

    if not unparsed:
        print("\n🎉 Nothing to do. All files are already parsed.")
        return

    # Only prompt for unparsed ones
    parsed_count = 0
    skipped_count = 0
    total_unparsed = len(unparsed)

    for p in unparsed:
        result = interactive_run_insert(str(p), garmin_file, conn, timezone_str=timezone_str)  # 3 args

        if result:
            parsed_count += 1
        elif result is False:
            skipped_count += 1
        elif result is None:
            print("\n🧾 Summary so far:")
            print(f"🔢 Total attempted: {parsed_count + skipped_count}")
            print(f"✅ Parsed: {parsed_count}")
            print(f"⏭️ Skipped: {skipped_count}")
            print(f"👋 Exited early before completing all {total_unparsed} files.")
            return

    print("\n🧾 Parsing complete.")
    print(f"🔢 Total unparsed files: {total_unparsed}")
    print(f"✅ Parsed: {parsed_count}")
    print(f"⏭️ Skipped: {skipped_count}")

    conn.close()

if __name__ == "__main__":
    main()
