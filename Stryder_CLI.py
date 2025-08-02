import argparse
import logging
from db_schema import connect_db, init_db
from batch_import import batch_process_stryd_folder
from find_unparsed_runs import main as find_unparsed_main
from reset_db import reset_db
from config import DB_PATH
from utils import prompt_for_timezone, get_paths_with_prompt, prompt_yes_no, interactive_run_insert
from pathlib import Path


VERSION = Path("version.txt").read_text().splitlines()[0].split(" - ")[0]


def main():
    parser = argparse.ArgumentParser(description="🏃 Stryder Run Manager CLI")
    parser.add_argument('--version', action='version', version=f'Stryder CLI v{VERSION}')
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

    # Sub-command: reset-db
    subparsers.add_parser("reset-db", help="⚠️ Delete all data from the database.")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    print(f"🌀 Stryder CLI v{VERSION}")

    if args.command == "find-unparsed":
        find_unparsed_main()
        return

    elif args.command == "reset-db":
        reset_db()
        return

    conn = connect_db(DB_PATH)

    if args.command == "init-db":
        init_db(conn)

    elif args.command == "add":
        init_db(conn)

        if args.batch:
            timezone_str = prompt_for_timezone()
            if timezone_str is None:
                print("❌ No timezone provided. Aborting import.")
                return

            if prompt_yes_no("📁 Use stored paths?"):
                stryd_path, garmin_file = get_paths_with_prompt()
                if stryd_path and garmin_file:
                    batch_process_stryd_folder(stryd_path, garmin_file, conn, timezone_str)
                else:
                    logging.warning("⚠️ Aborting batch: valid paths not provided.")
            else:
                logging.warning("⚠️ Batch mode requires valid paths.")


        elif args.single:
            if prompt_yes_no("📁 Use stored paths?"):
                stryd_path, garmin_file = get_paths_with_prompt()
                stryd_file = Path(stryd_path) / args.single
            else:
                stryd_folder = Path(input("📁 Enter STRYD folder path: ").strip())
                garmin_file = Path(input("📄 Enter Garmin CSV file: ").strip())
                stryd_file = stryd_folder / args.single

            result = interactive_run_insert(stryd_file, garmin_file, conn)
            if result is True:
                logging.info("✅ Single run added successfully.")
            elif result is False:
                logging.info("⏭️ Single run skipped.")
            elif result is None:
                logging.info("👋 User exited.")

    else:
        parser.print_help()
        return

    conn.close()


if __name__ == "__main__":
    main()
