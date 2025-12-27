import sqlite3
from pathlib import Path
import logging
import sys
from stryder_core.bootstrap import core_resolve_timezone, validate_path
from stryder_core.import_runs import single_process_stryd_file, batch_process_stryd_folder
from stryder_cli.cli_unparsed import find_unparsed_cli
from stryder_core.pipeline import insert_full_run
from stryder_core.runtime_context import set_context
from stryder_core.version import get_git_version
from stryder_core.config import DB_PATH
from stryder_core.db_schema import connect_db, init_db
from stryder_cli.reset_db import reset_db
from stryder_core.path_memory import REQUIRED_PATHS, CONFIG_PATH, save_json, load_json
from stryder_cli.prompts import prompt_valid_path, prompt_for_timezone, ensure_default_timezone


VERSION = get_git_version()


def _configure_matplotlib_backend():
    """ Auto-select a safe Matplotlib backend (GUI if available, else headless), unless user overrides. """
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

    data = load_json(CONFIG_PATH)
    resolved = {}

    # 1) Resolve/validate required paths
    for key, expect in REQUIRED_PATHS.items():
        raw = data.get(key)
        p = Path(raw).expanduser() if raw else None

        if not validate_path(p, expect):
            # Missing or invalid → prompt
            icon = "📄" if expect == "file" else "📁"
            p = prompt_valid_path(f"{icon} Path for {key} ({expect}): ", expect)
            # Store as POSIX for cross-OS friendliness (Windows accepts forward slashes)
            data[key] = p.as_posix()
            save_json(CONFIG_PATH, data)

        resolved[key] = p

    # 2) Timezone via existing helper (prompt once if needed)
    tz_str = ensure_default_timezone()  # e.g., returns "Europe/Athens" or similar
    tz_str, tzinfo = core_resolve_timezone(tz_str)

    # 3) Announce and set runtime context (so anything can read it later)
    stryd = resolved["STRYD_DIR"]
    garmin = resolved["GARMIN_CSV_FILE"]
    print(f"🧠 Defaults ➜ 📁 {stryd} | 📄 {garmin} | 🌍 {tz_str}")
    set_context(tz_str=tz_str, tzinfo=tzinfo, stryd_path=stryd, garmin_file=garmin)

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
    from stryder_cli.cli_utils import get_paths_with_prompt

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
        result = batch_process_stryd_folder(stryd_path, garmin_file, conn, tz)
        print("\n📊 Batch import complete.")
        print(f"   Total files: {result['files_total']}")
        print(f"   ✅ Parsed:   {result['parsed']}")
        print(f"   ⏭️ Skipped:  {result['skipped']}")
        return True

    # ---- SINGLE MODE BELOW ----
    elif mode == "single":
        if not single_filename:
            single_filename = input("📄 Enter STRYD CSV filename (e.g., 6747444.csv): ").strip()

        src = Path(single_filename)
        # respect absolute vs relative, like before
        stryd_file = src if src.is_absolute() else Path(stryd_path) / src

        result = single_process_stryd_file(stryd_file, garmin_file, conn, tz)
        status = result["status"]
        if status == "ok":
            summary = (
                f"Avg Power: {result['avg_power']:.2f} W/kg — "
                f"Avg HR: {result['avg_hr']} bpm — "
                f"Distance: {result['total_m'] / 1000:.2f} km"
            )

        if status == "file_not_found":
            print(f"❌ File not found: {result['file']}")
        elif status == "garmin_not_found":
            print(f"❌ Garmin CSV not found: {result['file']}")
        elif status == "already_exists":
            print(f"⚠️  Run at {result['start_time']} is already in the database. Not inserting again.")
        elif status == "skipped_no_garmin":
            print(f"⏭️ Skipped {result['file'].name} (no Garmin match within tolerance).")
        elif status == "zero_data":
            print(f"⏭️ Skipped {result['file'].name} — zero Stryd data.")
        elif status == "ok":
            insert_full_run(result["stryd_df"], result["workout_name"], notes="",
                            avg_power=result["avg_power"], avg_hr=result["avg_hr"],
                            total_m=result["total_m"], conn=conn)
            print(f"✅ Inserted: {result['file'].name} — {summary}")
        else:  # "error"
            print(f"❌ Failed to process {result['file'].name}: {result['error']}")

        return status == "inserted"

    else:
        return False

def launcher_menu(conn, metrics):
    """ The app's starting menu """
    from stryder_cli.cli_reports import reports_menu
    from stryder_cli.cli_queries import view_menu

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
           find_unparsed_cli()

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

    from stryder_core.metrics import build_metrics

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