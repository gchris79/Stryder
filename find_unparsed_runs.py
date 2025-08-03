import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
import tzlocal

from config import DB_PATH, GARMIN_CSV_FILE
from utils import convert_first_timestamp_to_str, get_paths_with_prompt, interactive_run_insert


def get_existing_datetimes(conn):
    cur = conn.cursor()
    cur.execute("SELECT datetime FROM runs")

    return {row[0] for row in cur.fetchall()}


def main():
    local_tz = ZoneInfo(tzlocal.get_localzone_name())
    stryd_path, _ = get_paths_with_prompt()
    folder = Path(stryd_path)

    conn = sqlite3.connect(str(DB_PATH))
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

    parsed_count = 0
    skipped_count = 0
    total_unparsed = len(unparsed)

    for file in unparsed:
        full_path = folder / file
        result = interactive_run_insert(full_path, GARMIN_CSV_FILE, conn)

        if result is True:
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


if __name__ == "__main__":
    main()
