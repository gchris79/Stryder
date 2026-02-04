import sqlite3
from datetime import datetime, timezone
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


def _sqlite_dt(x):
    """ Normalizes params for SQL use later """
    # If it's already a string, normalize common ISO forms
    if isinstance(x, str):
        s = x.replace("T", " ").replace("Z", "")
        # drop timezone offset if present (keeps 'YYYY-MM-DD HH:MM:SS')
        if "+" in s:
            s = s.split("+", 1)[0]
        if "-" in s[19:]:  # handles ...-02:00 offsets sometimes
            s = s[:19]
        return s[:19]

    # If it's a datetime, convert to UTC and drop tz, format as 'YYYY-MM-DD HH:MM:SS'
    if isinstance(x, datetime):
        if x.tzinfo is not None:
            x = x.astimezone(timezone.utc).replace(tzinfo=None)
        return x.strftime("%Y-%m-%d %H:%M:%S")

    return x


def build_window_query_and_params(start_utc, end_utc, keyword: str | None = None):
    """ Helper for fetch_runs_for_window to match the params with the query """
    params = [_sqlite_dt(start_utc), _sqlite_dt(end_utc)]

    query = fetch_runs_for_window(include_keyword=bool(keyword))

    if keyword:
        params.append(f"%{keyword}%")
    return query, tuple(params)


def fetch_runs_for_window(include_keyword: bool = False) -> str:
    """ SQL query for custom window reports """
    base = """
    SELECT 
        r.id AS run_id,
        r.datetime AS datetime_utc,
        r.duration_sec,
        r.distance_m AS meters,
        r.avg_power,
        r.avg_hr,
        w.workout_name,
        wt.name AS workout_type
    FROM runs r
    JOIN workouts w ON r.workout_id = w.id
    LEFT JOIN workout_types wt ON w.workout_type_id = wt.id
    WHERE r.datetime BETWEEN ? AND ?
    """
    if include_keyword:
        base += " AND w.workout_name LIKE ?"

    base += " ORDER BY r.datetime"

    return base


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
    page_size: int | None = 15,
):
    """ Takes a db connection a base query, base params, the last cursor and the page size
     a) gives option to return full table if no page size provided
     b) adds WHERE, AND if needed
     c) ads ORDER afterward
     d) checks if it's the end of the query or not
     e) returns rows, columns and cursor_next for the page """

    #TODO: This function will be deprecated. Cursor-based pagination; currently used only by CLI. TUI uses offset-based pagination instead.

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
        rows_for_page = rows[:page_size]
        last_displayed = rows_for_page[-1]

        cursor_next = (last_displayed["datetime"], last_displayed["run_id"])
        rows = rows_for_page
    else:
        cursor_next = None

    return rows, columns, cursor_next


def fetch_views_page(conn, base, page, base_params: tuple = (), page_size: int | None = 15):
    """ Takes a db connection a base query, base params, the current page and page size and
     a) sets off using current page and page size
     a) ads ORDER afterward
     b) uses limit and offset to map the page
     c) returns rows and columns for the page """

    offset = (page - 1) * page_size

    sql = f"""{base} ORDER BY r.datetime, r.id
                     LIMIT ? OFFSET ?"""
    params = base_params + (page_size, offset)
    rows, columns = _fetch(conn, sql, params)

    return rows, columns


def count_rows_for_query(conn, base_query:str, base_params:tuple = ()) -> int:
    """ Return the number of rows matching the query """
    sql = f"SELECT COUNT(*) FROM ({base_query})"
    cur = conn.execute(sql, base_params)
    return cur.fetchone()[0]