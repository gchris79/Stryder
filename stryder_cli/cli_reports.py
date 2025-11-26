from stryder_cli.cli_utils import MenuItem, prompt_menu
from stryder_core.reports import weekly_report, get_single_run_query
from stryder_cli.cli_queries import view_menu
from stryder_cli.prompts import input_date, input_positive_number, get_valid_input
from stryder_core.date_utilities import to_utc, dt_to_string
from stryder_core.formatting import fmt_str_decimals, fmt_hms
from stryder_core.runtime_context import get_tz_str, get_tzinfo
from stryder_cli.visualizations import display_menu


def reports_menu(conn, metrics):
    """ The reports menu """
    tz = get_tz_str()
    tzinfo = get_tzinfo()

    items1 = [
        MenuItem("1", "Last N weeks"),
        MenuItem("2", "N weeks ending on a date of your choice"),
        MenuItem("3", "Custom date range"),
        MenuItem("4", "Single run report")
    ]

    items2 = [
        MenuItem("1", "Rolling weeks (seven days from this day)"),
        MenuItem("2", "Calendar weeks (Monday - Sunday)" ),
    ]

    choice1 = prompt_menu("Reports", items1)
    # Fork for the type of the report single or batch
    if choice1 in ["1","2","3"]:
        df_type = "batch"
        # 1) Last N weeks
        if choice1 == "1":
            choice2 = prompt_menu("Group the weeks as", items2)
            if choice2 in ["1", "2"]:
                weeks = input_positive_number("How many weeks? ")
                mode = "rolling" if choice2 == "1" else "calendar"
                label, weekly_raw = weekly_report(conn, tz, mode=mode, weeks=weeks)
                display_menu(label, weekly_raw, df_type, metrics)

            elif choice1 == "b":
                return
            elif choice1 == "q":
                exit(0)

        # N weeks ending on a date of your choice
        elif choice1 == "2":
            choice2 = prompt_menu("Group the weeks as", items2)
            if choice2 in ["1", "2"]:
                weeks = input_positive_number("How many weeks? ")
                end_date = input("Give the end date of the report (YYYY-MM-DD): ")
                end_dt = to_utc(end_date, in_tz=tzinfo)
                mode = "rolling" if choice2 == "1" else "calendar"
                label, weekly_raw = weekly_report(conn, tz, mode=mode, weeks=weeks, end_date=end_dt)
                display_menu(label, weekly_raw, df_type, metrics)

            elif choice1 == "b":
                return
            elif choice1 == "q":
                exit(0)

        # Custom date range
        elif choice1 == "3":
            str_dt = input_date("Give the start date of the report (YYYY-MM-DD): ")
            end_dt = input_date("Give the end date of the report (YYYY-MM-DD): ")
            label, weekly_raw = weekly_report(conn, tz, mode="rolling", start_date=str_dt, end_date=end_dt)
            display_menu(label, weekly_raw, df_type, metrics)

    elif choice1 == "4":
        # Single run report
        df_type = "single"

        if (result := view_menu(conn, metrics,"for_report")) is None:      # Guard if user hits back without choosing run
            return                                           # Return to previous menu safely
        rows, columns = result              # Unpack safely

        cool_string = None
        if (run_id := get_valid_input("Please enter Run ID for the run you are interested in: ")) is None:
            return

        for row in rows:                    # Check users choice to match the run in table
            if int(row["run_id"]) == int(run_id):
                raw_ts = row["datetime"]                   # take the datetime of the run...
                dt_local = dt_to_string(to_utc(raw_ts, in_tz=tzinfo), "ymd_hms", tz=tzinfo)      # ...and localize it for display in cool string
                cool_string = (
                    f'\nRun {row["run_id"]} | {dt_local} | '
                    f'{row["wt_name"]} | {fmt_str_decimals(row["distance_m"]/1000)} km | {fmt_hms(row["duration"])}'
                )
                print(cool_string)      # print a cool string to show details about the picked run before the report

                df_raw = get_single_run_query(conn, run_id, metrics)
                if df_raw.empty:
                    print(f"Empty dataframe.")
                    return
                display_menu("",df_raw, df_type, metrics)
                break
        if cool_string is None:
            print(f"\nRun with Run ID {run_id} does not exist in you database.\n")

    elif choice1 == "b":
        return
        #menu_guard(None)

    elif choice1 == "q":
        exit(0)
