import logging
import sqlite3
import pandas as pd


def connect_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(conn):
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
        duration_sec INTEGER NOT NULL,
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
    cur = conn.cursor()
    cur.execute('''INSERT INTO workouts (workout_name, notes, workout_type_id) VALUES (?, ?, ?)''',(workout_name, notes, workout_type_id))
    conn.commit()
    return cur.lastrowid    # return new workout's ID


def get_or_create_workout_type(workout_type_name, conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM workout_types WHERE name = ?", (workout_type_name,))
    result = cur.fetchone()

    if result:
        return result[0]
    else:
        cur.execute("INSERT INTO workout_types (name) VALUES (?)", (workout_type_name,))
        conn.commit()
        return cur.lastrowid


def run_exists(conn, start_time_str):
    cur = conn.cursor()
    result = cur.execute(
        "SELECT id FROM runs WHERE datetime = ?",
        (start_time_str,)
    ).fetchone()
    return result is not None


def insert_run(workout_id, start_time, duration_sec, avg_hr, conn):
    cur = conn.cursor()

    start_time_str = start_time.isoformat(sep=' ', timespec='seconds')  # -> "2023-08-20 07:20:00"

    cur.execute('''INSERT INTO runs 
                (workout_id, datetime, duration_sec, avg_hr)
                VALUES (?, ?, ?, ?)''',(workout_id, start_time_str, duration_sec, avg_hr)
                )
    conn.commit()
    return cur.lastrowid


def insert_metrics(run_id, df, conn):
    cur = conn.cursor()
    rows = []

    # Check the input if its datetime object or string
    for i, row in df.iterrows():
        ts = row.get('Local Timestamp')

        if pd.isna(ts):
            if pd.isna(ts) or not hasattr(ts, 'isoformat'):
                continue

        rows.append((
            run_id,
            ts.isoformat(sep=' ', timespec='seconds'),
            row.get('Power (w/kg)'),
            row.get('Stryd Distance (meters)'),
            row.get('Ground Time (ms)'),
            row.get('Stiffness'),
            row.get('Cadence (spm)'),
            row.get('Vertical Oscillation (cm)')
        ))

    cur.executemany('''
        INSERT INTO metrics (
            run_id, datetime, power, stryd_distance,
            ground_time, stiffness, cadence, vertical_oscillation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)

    conn.commit()
