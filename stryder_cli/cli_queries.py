from typing import Literal

from stryder_cli.cli_utils import MenuItem, menu_guard, prompt_menu, print_list_table
from stryder_core.queries import fetch_page, views_query, for_report_query
from stryder_cli.prompts import input_date, prompt_yes_no
from stryder_core.formatting import format_view_columns


def paginate_runs(conn, base_query, mode, metrics, base_params=(), page_size: int = 20):
    """ The main function for pagination
    a) stores cursors for going back
    b) take columns, rows and cursor sends them to be formatted
    c) prints the table
    d) adds the appropriate UI to navigate through the pages """
    stack = []             # cursors for going back
    cursor = None          # current cursor (None means first page)
    while True:
        rows, columns, cursor_next = fetch_page(
            conn, base_query, base_params=base_params,
            last_cursor=cursor, page_size=page_size)

        if not rows and not stack and cursor is None:
            print(" ⚠️ No results."); return "no_results"

        headers, formatted_rows = format_view_columns(rows,mode, metrics)
        print_list_table(formatted_rows, headers)

        # Determine navigation availability
        at_start = (len(stack) == 0)
        at_end = (cursor_next is None)

        # Build dynamic prompt
        options = []
        if not at_end: options.append("[n]ext")
        if not at_start: options.append("[p]rev")
        options.append("[q]uit")
        prompt = " ".join(options) + ": "

        while True:
            cmd = input(prompt).strip().lower()
            if cmd == "q":
                return "quit"
            elif cmd in ("n", ""):
                if at_end:
                    if mode == "for_report":
                        if prompt_yes_no("Do you want to exit and choose a run for report?"):
                            return "choose_run"
                        else: continue
                    else:
                        print("Already at the last page."); continue
                stack.append(cursor)
                cursor = cursor_next; break
            elif cmd == "p":
                if at_start:
                    print("Already at first page"); continue
                cursor = stack.pop(); break
            else:
                print(" ⚠️ Not a valid input."); continue


def get_all_workouts(conn, metrics, mode):
    """ Get all runs from the database """
    base_query = views_query() if mode == "for_views" else for_report_query()
    paginate_runs(conn, base_query, mode, metrics)
    return fetch_page(conn, base_query, page_size=0)        # Return the full table for report


def get_workouts_by_date(date1, date2, conn, metrics, mode):
    """ Return workouts filtered by date """
    base_query = views_query() if mode == "for_views" else for_report_query()
    base_query += " WHERE r.datetime BETWEEN ? AND ?"
    base_params = (date1, date2)
    paginate_runs(conn, base_query, mode, metrics, base_params=base_params)
    return fetch_page(conn,base_query,base_params,page_size=0)      # Return the full table for report


def get_workouts_by_keyword(keyword, conn, metrics, mode):
    """ Return workouts filtered by keyword """
    like_term = f"%{keyword}%"
    if mode == "for_views":
        base_query = views_query() + " WHERE (w.workout_name LIKE ? OR wt.name LIKE ?)"
        base_params = (like_term, like_term)
        paginate_runs(conn, base_query, mode, metrics, base_params=base_params)
        return fetch_page(conn, base_query, base_params, page_size=0)

    elif mode == "for_report":
        base_query = for_report_query() + " WHERE w.workout_name LIKE ?"
        base_params = (like_term,)
        paginate_runs(conn, base_query, mode, metrics, base_params=base_params)
        return fetch_page(conn, base_query, base_params, page_size=0)

    else: return print(f"⚠️ Not a valid view mode (must be 'for_report' or 'for_views')")


def view_menu(conn, metrics, mode : Literal["for_views", "for_report"]):
    """ The menu of views """

    items1 = [
        MenuItem("1", "All runs"),
        MenuItem("2", "Runs by date"),
        MenuItem("3", "Runs by keyword"),
    ]

    choice1 = prompt_menu("View Runs", items1)

    if choice1 == "1":
        rows, columns, _ = get_all_workouts(conn, metrics, mode)
        return menu_guard(rows, columns)

    elif choice1 == "2":
        start_dt = input_date("Start date (YYYY-MM-DD): ")
        end_dt = input_date("End date (YYYY-MM-DD): ")
        start_full = start_dt.strftime("%Y-%m-%d 00:00:00")
        end_full = end_dt.strftime("%Y-%m-%d 23:59:59")
        rows, columns, _ = get_workouts_by_date(start_full, end_full, conn, metrics, mode)
        return menu_guard(rows, columns)

    elif choice1 == "3":
        keyword = input("Search workouts by keyword: ")
        rows, columns, _ = get_workouts_by_keyword(keyword, conn, metrics, mode)
        return menu_guard(rows, columns)


    elif choice1 == "b":
        return None

    elif choice1 == "q":
        exit(0)
