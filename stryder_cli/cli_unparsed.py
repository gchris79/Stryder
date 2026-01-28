import logging
import sqlite3
from pathlib import Path
from stryder_cli.prompts import prompt_for_timezone
from stryder_core.config import DB_PATH
from stryder_core.find_unparsed_runs import find_unparsed_files
from stryder_cli.cli_utils import get_paths_with_prompt, MenuItem, prompt_menu
from stryder_core.pipeline import insert_full_run
from stryder_core.import_runs import prepare_run_insert


def find_unparsed_cli():
    """ Asks user for tz, gets Stryd/Garmin files, gets the results for unparsed runs and outputs to user a report """

    timezone_str = input("🌍 Please, add a timezone for these runs (e.g. Europe/Athens): ").strip()

    stryd_folder, garmin_file = get_paths_with_prompt()

    conn = sqlite3.connect(DB_PATH)
    result = find_unparsed_files(stryd_folder, conn)

    total_files = result["total_files"]
    unparsed_files = result["unparsed_files"]
    parsed_files = result["parsed_files"]

    print(f"\n✅ Total STRYD files found: {total_files}")
    print(f"✅ Parsed files in DB: {parsed_files}")
    print(f"❗ Unparsed files: {len(unparsed_files)}")

    if not unparsed_files:
        print("\n🎉 Nothing to do. All files are already parsed.")
        return

    # Run interactive step:
    parsed_count = 0
    skipped_count = 0

    for file in unparsed_files:
        result = interactive_run_insert_cli(str(file), garmin_file, conn, timezone_str)
        if result:
            parsed_count += 1
        elif result is False:
            skipped_count += 1
        elif result is None:
            print("\n🧾 Summary so far:")
            print(f"🔢 Total attempted: {parsed_count + skipped_count}")
            print(f"✅ Parsed: {parsed_count}")
            print(f"⏭️ Skipped: {skipped_count}")
            print(f"👋 Exited early before completing all {len(unparsed_files)} files.")
            conn.close()
            return

    print("\n🧾 Parsing complete.")
    print(f"🔢 Total unparsed files: {len(unparsed_files)}")
    print(f"✅ Parsed: {parsed_count}")
    print(f"⏭️ Skipped: {skipped_count}")

    conn.close()


def interactive_run_insert_cli(stryd_file, garmin_file, conn, timezone_str=None) -> bool | None:
    """ Prompts for timezone, gets info about the run and handles cases if it matches
        a) if it matches Garmin, b) if not but get parsed anyway, c) if it's already in db
        d) if it's skipped by the user, or e) there is input error """
    file_name = Path(stryd_file).name

    while True:
        if timezone_str is None:
            tz_input = prompt_for_timezone(stryd_file)
            if tz_input == "EXIT":
                logging.info("👋 User exited early.")
                return None
            # for invalid or None timezone values
            if not tz_input:
                return None
            timezone_str = tz_input

        # Call core to do the work
        result = prepare_run_insert(stryd_file, garmin_file, file_name, conn, timezone_str)

        # Garmin not matched → show menu
        if result["status"] == "no_garmin":
            print(f"\n❌ No Garmin match found for {file_name}.")
            items = [
                MenuItem("1", "Parse anyway without Garmin match"),
                MenuItem("2", "Try another timezone"),
                MenuItem("3", "Skip for now")
                ]
            choice = prompt_menu("What would you like to do", items, allow_back=False)

            if choice == "1":
                insert_full_run(result["stryd_df"], result["workout_name"], notes="",avg_power=result["avg_power"], avg_hr=None,total_m=result["total_m"], conn=conn)
                logging.info(f"✅ Inserted without Garmin match: {stryd_file}")
                return True

            elif choice == "2":
                # force a re-prompt next loop
                timezone_str = None
                continue

            elif choice == "3":
                logging.info(f"⏭️ Skipped: {file_name}")
                result["status"] = "skipped"
                return False

            elif choice == "q":
                logging.info("👋 Exiting early.")
                return None

            else:
                print("❓ Invalid choice. Try again.")
                continue

        elif result["status"] == "ok":
            insert_full_run(result["stryd_df"], result["workout_name"], notes="",
                            avg_power=result["avg_power"], avg_hr=result["avg_hr"],
                            total_m=result["total_m"], conn=conn)
            return True

        elif result["status"] == "skipped":
            return False

        elif result["status"] == "error":
            return False

        elif result["status"] == "already_exists":
            print(f"⚠️ Run already exists in DB: {file_name}")
            return False

        elif result["status"] == "zero_data":
            print(f"⚠️ Stryd data is incomplete (zero distance/speed). Run skipped.")
            return False

        else:
            logging.error(f"Unexpected status in run insert: {result['status']}")
            return None
