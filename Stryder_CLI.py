import argparse
import logging
from version import get_git_version
from pathlib import Path
from db_schema import connect_db, init_db
from batch_import import batch_process_stryd_folder
from find_unparsed_runs import main as find_unparsed_main
from reset_db import reset_db
from config import DB_PATH
from utils import prompt_for_timezone, get_paths_with_prompt
from pipeline import process_csv_pipeline, insert_full_run
from queries import view_menu
from summaries import summary_menu

VERSION = get_git_version()
DEFAULT_TIMEZONE = "Europe/Athens"      # or None for auto-local

# Early parser for --debug switch
debug_parser = argparse.ArgumentParser(add_help=False)
debug_parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
args, remaining_argv = debug_parser.parse_known_args()

# Set logging level based on --debug
if args.debug:
    print("🔧 Debug mode enabled")
logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


def add_import_menu(conn, mode: str | None = None, single_filename: str | None = None) -> bool:
    # 1) Timezone once
    tz = prompt_for_timezone()
    if not tz or tz == "EXIT":
        print("⚠️ Aborted: no valid timezone provided.")
        return False

    # 2) Paths once
    stryd_path, garmin_file = get_paths_with_prompt()
    if not (stryd_path and garmin_file):
        print("⚠️ Aborted: paths not provided.")
        return False

    # 3) Choose mode
    if mode not in ("batch", "single"):
        print("\nWhat do you want to import?")
        print("  1) Entire STRYD folder (batch)")
        print("  2) A single STRYD file")
        choice = input("Choose 1 or 2: ").strip()
        mode = "batch" if choice != "2" else "single"

    if mode == "batch":
        # Your batch function only logs; don’t rely on local counters.
        batch_process_stryd_folder(stryd_path, garmin_file, conn, tz)
        print("\n📊 Batch complete. (See logs for totals)")
        return True

    # ---- SINGLE MODE BELOW ----
    # Define names **before** try/except so error prints never reference undefined vars
    if not single_filename:
        single_filename = input("📄 Enter STRYD CSV filename (e.g., 6747444.csv): ").strip()

    src = Path(single_filename)
    src_name = src.name
    stryd_file = src if src.is_absolute() else Path(stryd_path) / src

    if not stryd_file.exists():
        print(f"❌ File not found: {stryd_file}")
        return False

    try:
        stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m = process_csv_pipeline(
            str(stryd_file), garmin_file, tz
        )
        # Derive workout name if present
        workout_name = (
            stryd_df["Workout Name"].iloc[0]
            if "Workout Name" in stryd_df.columns and len(stryd_df) > 0
            else "Unknown"
        )
        insert_full_run(stryd_df, workout_name, "", avg_power, avg_hr, total_m, conn)
        print(f"✅ Inserted: {src_name} - {total_m/1000:.2f} km")
        return True
    except Exception as e:
        # Use src_name so we don't depend on stryd_file being in scope
        print(f"❌ Failed to process {src_name}: {e}")
        return False


def launcher_menu():
    while True:
        print("\n🏁 What would you like to do?")
        print("[1] Add (batch)")
        print("[2] Find unparsed")
        print("[3] View")
        print("[4] Summary")
        print("[5] Reset DB")
        print("[q] Quit")
        choice = input("> ").strip().lower()

        if choice == "1":
            conn = connect_db(DB_PATH); init_db(conn)
            try:
                add_import_menu(conn)
            finally:
                conn.close()

        elif choice == "2":
            find_unparsed_main()

        elif choice == "3":
            conn = connect_db(DB_PATH); init_db(conn)
            try:
                view_menu()
            finally:
                conn.close()

        elif choice == "4":
            conn = connect_db(DB_PATH); init_db(conn)
            try:
                summary_menu()
            finally:
                conn.close()

        elif choice == "5":
            reset_db()

        elif choice in {"q", "x"}:
            break
        else:
            print("❓ Not a choice. Try again.")

def main():
    parser = argparse.ArgumentParser(
        prog=f"🏃 Stryder CLI v{VERSION}",
        description="Your running data CLI",
        parents=[debug_parser] # Inherit debug flag
    )

    print(f"🏃 Stryder CLI v{VERSION}")
    parser.add_argument("--version", action="version", version=f"Stryder CLI v{VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    # Sub-command: init-db
    subparsers.add_parser("init-db", help="Initialize the database schema.")

    # Sub-command: add
    add_parser = subparsers.add_parser("add", help="Add new Stryd runs (single or batch)")
    add_group = add_parser.add_mutually_exclusive_group(required=True)
    add_group.add_argument("-b", "--batch", action="store_true", help="Batch import all Stryd files")
    add_group.add_argument("-s", "--single", type=str, metavar="FILE", help="Import a single Stryd CSV file")

    # Sub-command: find-unparsed
    subparsers.add_parser("find-unparsed", help="List unparsed Stryd files that are not in the database.")

    # Sub-command: view-workouts
    subparsers.add_parser("view", help="View your workouts.")

    # Sub-command: summary-workouts
    parser_summary = subparsers.add_parser("summary", help="Aggregate summaries")
    parser_summary.add_argument("--period", choices=["week", "last7", "4weeks"], required=True)
    parser_summary.add_argument("--tz", default="Europe/Athens")

    # Sub-command: reset-db
    subparsers.add_parser("reset-db", help="⚠️ Delete all data from the database.")

    args = parser.parse_args(remaining_argv)  # use leftover args


    if args.command is None:
        launcher_menu()
        return

    if args.command == "find-unparsed":
        find_unparsed_main()
        return

    elif args.command == "reset-db":
        reset_db()
        return

    conn = connect_db(DB_PATH)

    if args.command == "init-db":
        init_db(conn)

    elif args.command == "view":
        init_db(conn)
        view_menu()

    elif args.command == "summary":
        from summaries import _show_summary
        if args.period == "week":
            _show_summary(connect_db(DB_PATH), "week_completed", args.tz)
        elif args.period == "last7":
            _show_summary(connect_db(DB_PATH), "rolling_7d", args.tz)
        else:
            _show_summary(connect_db(DB_PATH), "rolling_4w", args.tz)


    elif args.command == "add":
        init_db(conn)

        if args.batch:
            add_import_menu(conn, mode="batch")

        elif args.single:
            add_import_menu(conn, mode="single", single_filename=args.single)

        else:
            # no flag? fall back to interactive choice
            add_import_menu(conn)

    else:
        parser.print_help()
        return

    conn.close()


if __name__ == "__main__":
    main()