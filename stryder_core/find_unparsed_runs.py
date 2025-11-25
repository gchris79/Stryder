import logging
import pandas as pd
from pathlib import Path
from stryder_core.metrics import align_df_to_metric_keys, STRYD_PARSE_SPEC


def get_existing_datetimes(conn):
    """ Returns first row datetime from runs table """
    cur = conn.cursor()
    cur.execute("SELECT datetime FROM runs")
    return {row[0] for row in cur.fetchall()}


def convert_first_timestamp_to_str(file_path):
    """ Creates a dataframe from file takes the earliest sample """
    df = pd.read_csv(file_path)
    df = align_df_to_metric_keys(df, STRYD_PARSE_SPEC, keys={"timestamp_s"})
    if 'timestamp_s' not in df.columns or df['timestamp_s'].empty:
        raise ValueError("Missing or empty 'timestamp_s' column")

    # Parse as UTC (tz-aware) and pick the earliest sample
    ts = pd.to_datetime(df['timestamp_s'], unit='s', utc=True).min()

    # Store/compare in UTC to match how runs.datetime is saved in the DB
    return ts.isoformat(sep=' ', timespec='seconds')


def find_unparsed_files(stryd_folder: Path, conn) -> dict:
    """Return a list of Stryd CSV files that are not in the DB yet."""
    existing = get_existing_datetimes(conn) # set of strings
    unparsed = []
    total_files = 0

    for file in stryd_folder.glob("*.csv"):
        total_files += 1
        try:
            ts_str = convert_first_timestamp_to_str(file)
        except Exception:
            logging.warning(f"Failed to inspect {file.name}: {e}")
            # treat unreadable as unparsed
            unparsed.append(file)
            continue

        if ts_str not in existing:
            unparsed.append(file)

    return {
        "mode": "find_unparsed",
        "total_files": total_files,
        "unparsed_files": unparsed,
        "parsed_files": total_files - len(unparsed),
    }