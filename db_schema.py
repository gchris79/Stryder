import logging
import sqlite3
import pandas as pd
from date_utilities import to_utc


def connect_db(db_path):
    """ Gets the connection with the database and returns it """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(conn):
    """ Creates the DB if not already exists """
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS workout_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_name TEXT NOT NULL,
        notes TEXT,
        workout_type_id INTEGER, 
        FOREIGN KEY (workout_type_id) REFERENCES workout_types(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER,
        datetime TEXT NOT NULL,
        avg_power REAL,
        duration_sec INTEGER NOT NULL,
        distance_m REAL,
        avg_hr INTEGER,
        FOREIGN KEY (workout_id) REFERENCES workouts(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        datetime TEXT NOT NULL,
        power REAL,
        stryd_distance REAL,
        ground_time REAL,
        stiffness REAL,
        cadence REAL,
        vertical_oscillation REAL,
        FOREIGN KEY (run_id) REFERENCES runs(id)
    );
    """)

    conn.commit()
    logging.info("✅ Database initialized.")


def insert_workout(workout_name, notes, workout_type_id, conn):
    """ Inserts the workout name and returns its ID """
    cur = conn.cursor()
    cur.execute('''INSERT INTO workouts (workout_name, notes, workout_type_id) VALUES (?, ?, ?)''',(workout_name, notes, workout_type_id))
    conn.commit()
    return cur.lastrowid    # return new workout's ID


def get_or_create_workout_type(workout_type_name, conn):
    """ Looks for workout type and returns its ID, if there is none it creates it """
    cur = conn.cursor()
    cur.execute("SELECT id FROM workout_types WHERE name = ?", (workout_type_name,))
    result = cur.fetchone()

    if result:
        return result[0]
    else:
        cur.execute("INSERT INTO workout_types (name) VALUES (?)", (workout_type_name,))
        conn.commit()
        return cur.lastrowid


def run_exists(conn, start_time, *, in_tz=None):
    """ Return True if a run with the given start_time exists in the DB """
    # Naive inputs are interpreted in `in_tz` (default UTC) and normalized to UTC
    dt_utc = to_utc(start_time, in_tz=in_tz).replace(microsecond=0)
    # Matches DB format: 'YYYY-MM-DD HH:MM:SS' (UTC, second precision)
    start_time_str = dt_utc.isoformat(sep=' ', timespec='seconds')

    cur = conn.cursor()
    row = cur.execute(
        "SELECT id FROM runs WHERE datetime = ? LIMIT 1",
        (start_time_str,)
    ).fetchone()
    return row is not None


def insert_run(workout_id, start_time, avg_power, duration_sec, avg_hr, distance_m, conn, *, in_tz=None):
        """ Checks if start_time is in UTC, inserts row, returns row id """
        # Ensure start_time is stored in UTC, kills microseconds if any
        dt_utc = to_utc(start_time, in_tz=in_tz).replace(microsecond=0)
        # Formats it to db format
        start_time_str = dt_utc.isoformat(sep=' ', timespec='seconds')

        cur = conn.cursor()
        try:
            cur.execute('''INSERT INTO runs 
                    (workout_id, datetime, avg_power, duration_sec, avg_hr, distance_m)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (workout_id, start_time_str, avg_power, duration_sec, avg_hr, distance_m)
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # Duplicate timestamp → fetch existing id
            row = conn.execute("SELECT id FROM runs WHERE datetime = ? LIMIT 1", (start_time_str,)).fetchone()
            return row[0] if row else None


def insert_metrics(run_id, df, conn):
    """ Takes dt column from df, checks if its dt or string, appends metrics row """
    cur = conn.cursor()
    rows = []

    # Check the input if its datetime object or string
    for i, row in df.iterrows():
        ts = row.get('ts_local')

        if pd.isna(ts) or not hasattr(ts, 'isoformat'):
            continue

        rows.append((
            run_id,
            ts.isoformat(sep=' ', timespec='seconds'),
            row.get('power_sec'),
            row.get('str_dist_m'),
            row.get('ground'),
            row.get('stiffness'),
            row.get('cadence'),
            row.get('vo')
        ))

    cur.executemany('''
        INSERT INTO metrics (
            run_id, datetime, power, stryd_distance,
            ground_time, stiffness, cadence, vertical_oscillation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)

    conn.commit()