import logging
import sys

from file_parsing import ZeroStrydDataError
from version import get_git_version
from pathlib import Path
from path_memory import load_last_used_paths, save_last_used_paths
from db_schema import connect_db, init_db
from batch_import import batch_process_stryd_folder
from find_unparsed_runs import main as find_unparsed_main
from reset_db import reset_db
from config import DB_PATH
from utils import prompt_for_timezone, get_paths_with_prompt, ensure_default_timezone
from pipeline import process_csv_pipeline, insert_full_run
from queries import view_menu
from summaries import summary_menu


VERSION = get_git_version()


# Set logging level based on --debug
def configure_logging():
    debug = ("--debug" in sys.argv) or ("-d" in sys.argv)
    if debug:
        print("🔧 Debug mode enabled")
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _bootstrap_defaults_interactive():
    """If any of STRYD path, Garmin file, or timezone is missing, ask once and store."""
    stryd, garmin, tz = load_last_used_paths()

    if stryd and garmin and tz:
        # Optional: echo what we’ll use
        print(f"🧠 Defaults ➜ 📁 {stryd} | 📄 {garmin} | 🌍 {tz}")
        return

    print("⚙️  First-time setup (store defaults):")
    if not stryd:
        stryd = Path(input("📁 STRYD folder path: ").strip())
        stryd.mkdir(parents=True, exist_ok=True)
    if not garmin:
        garmin = Path(input("📄 Garmin CSV file path: ").strip())
    if not tz:
        tz = ensure_default_timezone()
        if not tz:
            print("⚠️ No timezone provided. You can set it later; using prompts may appear.")
    save_last_used_paths(stryd_path=stryd, garmin_file=garmin, timezone=tz)


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
        print("  [1] Entire STRYD folder (batch)")
        print("  [2] A single STRYD file")
        choice = input("Choose 1 or 2: ").strip()
        if choice == "1":
            mode = "batch"
        elif choice == "2":
            mode = "single"
        else:
            print("❓ Invalid choice. Try again.")
            return False

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
        print(f"✅ Inserted: {src_name} -Avg. Power: {avg_power} - Avg.HR: {avg_hr} - {total_m/1000:.2f} km")
        return True

    except ZeroStrydDataError as e:
        logging.info(f"⏭️  Skipped: {Path(stryd_file).name} — {e}")
        return False

    except Exception as e:
        # Use src_name so we don't depend on stryd_file being in scope
        print(f"❌ Failed to process {src_name}: {e}")
        return False


def launcher_menu():
    while True:
        print("\n🏁 What would you like to do?")
        print("[1] Add run to DB (batch or single)")
        print("[2] Find unparsed runs")
        print("[3] View parsed runs")
        print("[4] Summaries")
        print("[5] Reset DB")
        print("[q] Quit")
        choice = input("> ").strip().lower()

        # Options that no DB is needed
        if choice in {"2", "q", "x"}:
            if choice == "2":
                find_unparsed_main()

            elif choice in {"q", "x"}:
                break

        # Options that need DB
        elif choice in {"1", "3", "4", "5"}:
            conn = connect_db(DB_PATH)

            if choice == "1":
                add_import_menu(conn)

            elif choice == "3":
                view_menu(conn)

            elif choice == "4":
                summary_menu(conn)

            elif choice == "5":
                reset_db(conn)

            conn.close()
        else:
            print("❓ Not a choice. Try again.")


def main():

    configure_logging()
    print(f"\n🏃 Stryder CLI v{VERSION}")
    print("Your running data CLI\n")
    conn = connect_db(DB_PATH)
    try:
        init_db(conn)
    finally:
        conn.close()

    _bootstrap_defaults_interactive()
    launcher_menu()


if __name__ == "__main__":
    main()