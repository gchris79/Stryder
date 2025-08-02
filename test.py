import sqlite3
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
import tzlocal

from config import DB_PATH, STRYD_FOLDER


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


if __name__ == "__main__":
    main()