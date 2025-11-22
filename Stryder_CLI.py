import sqlite3
from pathlib import Path
import logging
import sys
from version import get_git_version
from config import DB_PATH
from db_schema import connect_db, init_db, run_exists
from reset_db import reset_db
from file_parsing import ZeroStrydDataError
from utils import loadcsv_2df
from path_memory import REQUIRED_PATHS, CONFIG_PATH, prompt_valid_path, \
    save_json, load_json
import runtime_context



VERSION = get_git_version()


def _configure_matplotlib_backend():
    import os, sys, matplotlib
    if os.environ.get("MPLBACKEND"):
        return  # respect user override
    try:
        if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
            matplotlib.use("TkAgg")  # GUI
        else:
            matplotlib.use("Agg")    # headless fallback (saves files)
    except Exception as e:
        print("[plot] Backend selection error:", e)

_configure_matplotlib_backend()

def bootstrap_defaults_interactive() -> dict[str, Path]:
    """
    - Loads last used paths from ~/.stryder/last_used_paths.json
    - Validates them; if missing/invalid, prompts once and resaves
    - Resolves timezone via helper (no tz stored here)
    - Sets runtime_context with tz + paths
    - Returns a dict of usable Path objects
    """
    from date_utilities import resolve_tz, ensure_default_timezone

    data = load_json(CONFIG_PATH)
    resolved: dict[str, Path] = {}

    # 1) Resolve/validate required paths
    for key, expect in REQUIRED_PATHS.items():
        raw = data.get(key)
        p = Path(raw).expanduser() if raw else None

        if not p or not p.exists() or (expect == "file" and not p.is_file()) or (expect == "dir" and not p.is_dir()):
            # Missing or invalid → prompt
            icon = "📄" if expect == "file" else "📁"
            p = prompt_valid_path(f"{icon} Path for {key} ({expect}): ", expect)
            # Store as POSIX for cross-OS friendliness (Windows accepts forward slashes)
            data[key] = p.as_posix()
            save_json(CONFIG_PATH, data)

        resolved[key] = p

    # 2) Timezone via existing helper (prompt once if needed)
    tz_str = ensure_default_timezone()  # e.g., returns "Europe/Athens" or similar
    tzinfo = resolve_tz(tz_str) if tz_str else None

    # 3) Announce and set runtime context (so anything can read it later)
    stryd = resolved["STRYD_DIR"]
    garmin = resolved["GARMIN_CSV_FILE"]
    print(f"🧠 Defaults ➜ 📁 {stryd} | 📄 {garmin} | 🌍 {tz_str}")
    runtime_context.set_context(tz_str=tz_str, tzinfo=tzinfo, stryd_path=stryd, garmin_file=garmin)

    return resolved


def configure_connection(conn: sqlite3.Connection) -> None:
    """Call this once after opening the DB so rows are dict-like."""
    conn.row_factory = sqlite3.Row



def configure_logging():
    """ Set logging level based on --debug """
    debug = ("--debug" in sys.argv) or ("-d" in sys.argv)
    if debug:
        print("🔧 Debug mode enabled")
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def add_import_menu(conn, mode: str | None = None, single_filename: str | None = None) -> bool:
    """ The main import run option, gets tz, file paths and mode and prompts for batch or single run import"""
    from date_utilities import prompt_for_timezone
    from utils import get_paths_with_prompt
    from batch_import import batch_process_stryd_folder
    from pipeline import process_csv_pipeline, insert_full_run

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
            print("❓ Invalid choice. Exiting to main menu...")
            return False

    # ---- BATCH MODE BELOW ----
    if mode == "batch":
        # Batch function only logs; don’t rely on local counters.
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
    # Transform Stryd and Garmin csv's to dataframes
    stryd_raw_df = loadcsv_2df(stryd_file)
    garmin_raw_df = loadcsv_2df(garmin_file)


    try:
        stryd_df, duration_td, avg_power, duration_str, avg_hr, total_m = process_csv_pipeline(
            stryd_raw_df, garmin_raw_df, tz, stryd_file.name
        )

        start_time_str = stryd_df['ts_local'].iloc[0].isoformat(sep=' ', timespec='seconds')
        # Check if run already exists
        if run_exists(conn, start_time_str):
            logging.warning(f"⚠️  Run at {start_time_str} already exists. Skipping.")
            print(f"⚠️ Run at {start_time_str} is already in the database. Not inserting again.")
            return False

        # Derive workout name if present
        workout_name = (
            stryd_df["wt_name"].iloc[0]
            if "wt_name" in stryd_df.columns and len(stryd_df) > 0
            else "Unknown"
        )
        insert_full_run(stryd_df, workout_name, "", avg_power, avg_hr, total_m, conn)
        print(f"✅ Inserted: {src_name} - Avg. Power: {avg_power} - Avg.HR: {avg_hr} - {total_m/1000:.2f} km")
        return True

    except ZeroStrydDataError as e:
        logging.info(f"⏭️  Skipped: {Path(stryd_file).name} — {e}")
        return False

    except Exception as e:
        # Use src_name so we don't depend on stryd_file being in scope
        print(f"❌ Failed to process {src_name}: {e}")
        return False


def launcher_menu(conn, metrics):
    """ The app's starting menu """
    from reports import reports_menu
    from find_unparsed_runs import main as find_unparsed_main
    from queries import view_menu

    while True:
        print("\n🏁 What would you like to do?")
        print("[1] Add run to DB (batch or single)")
        print("[2] Find unparsed runs")
        print("[3] View parsed runs")
        print("[4] Reports")
        print("[5] Reset DB")
        print("[q] Quit")
        choice = input("> ").strip().lower()

        if choice == "1":
            add_import_menu(conn)

        elif choice == "2":
           find_unparsed_main()

        elif choice == "3":
            view_menu(conn, metrics, "for_views")

        elif choice == "4":
            reports_menu(conn, metrics)

        elif choice == "5":
            reset_db(conn)

        elif choice in {"q", "x"}:
            break
        else:
            print("❓ Not a choice. Try again.")


def main():

    configure_logging()
    print(f"\n🏃 Stryder CLI v{VERSION}")
    print("Your running data CLI\n")

    paths = bootstrap_defaults_interactive()            # Get saved tz, paths, etc.

    from metrics import build_metrics

    metrics = build_metrics("local")            # Build metrics dict

    conn = connect_db(DB_PATH)                  # Open db + configure row access by name
    configure_connection(conn)

    try:
        init_db(conn)
        launcher_menu(conn, metrics)            # Pass the connection and METRICS along the menus

    finally:
        conn.close()                            # Close the connection

if __name__ == "__main__":
    main()