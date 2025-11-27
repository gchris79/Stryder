import sqlite3
from typing import Tuple, List


def views_query() -> str:
    """ SQL query for views table """
    return """
        SELECT 
            r.id            AS run_id,
            r.datetime      AS datetime,
            w.workout_name  AS wt_name,
            r.distance_m    AS distance_m,
            r.duration_sec  AS duration_sec,
            r.avg_power     AS avg_power,
            r.avg_hr        AS avg_hr,
            wt.name         AS wt_type
        FROM runs r
        JOIN workouts w ON r.workout_id = w.id
        JOIN workout_types wt ON w.workout_type_id = wt.id
    """

def for_report_query() -> str:
    """ SQL query for weekly reports table """
    return""" 
        SELECT
            r.id            AS run_id,
            r.datetime      AS datetime,
            w.workout_name  AS wt_name,
            r.duration_sec  AS duration,
            r.distance_m    AS distance_m
        FROM runs r
        JOIN workouts w ON r.workout_id = w.id
    """


def _fetch(conn: sqlite3.Connection, sql: str, params: tuple = ()
           ) -> Tuple[List[sqlite3.Row], List[str]]:
    """ Execute a SQL SELECT query and return (rows, column_names) in the order returned by SQLite. """
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description]  # SELECT order
    return rows, columns


def fetch_page(
    conn,
    base,
    base_params: tuple = (),
    last_cursor: tuple | None = None,    # cursor: (last_datetime_iso, last_id)
    page_size: int | None = 20,
):
    """ Takes a db connection a base query, base params, the last cursor and the page size
     a) gives option to return full table if no page size provided
     b) adds WHERE, AND if needed
     c) ads ORDER afterward
     d) checks if it's the end of the query or not
     e) returns rows, columns and cursor_next for the page """

    # No pagination: return the full table, ignore cursor/lookahead
    if not page_size:  # 0 or None
        sql = f"{base} ORDER BY r.datetime, r.id"
        rows, columns = _fetch(conn, sql, base_params)
        return rows, columns, None

    limit = page_size + 1       # lookahead

    # If base_query has WHERE -> append AND; otherwise start WHERE
    has_where = " WHERE " in base.upper()
    joiner = " AND " if has_where else " WHERE "

    if last_cursor is None:
        sql = f"{base} ORDER BY r.datetime, r.id LIMIT ?"
        params = (*base_params, limit)
    else:
        last_dt, last_id = last_cursor
        sql = (
            f"{base}{joiner}"
            "((r.datetime > ?) OR (r.datetime = ? AND r.id > ?))"
            "ORDER BY r.datetime, r.id LIMIT ?"
        )
        params = (*base_params, last_dt, last_dt, last_id, limit)

    # params order: where params + cursor params + limit
    rows, columns = _fetch(conn, sql, params)

    # Lookahead handling
    if len(rows) == limit:
        last = rows[-1]
        cursor_next = (last["datetime"], last["run_id"])
        rows = rows[:-1]  # trim the lookahead row from current page
    else:
        cursor_next = None

    return rows, columns, cursor_next