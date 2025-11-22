from dataclasses import dataclass
from typing import Callable, Iterable, Optional
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from tabulate import tabulate
from date_utilities import prompt_for_timezone
from path_memory import save_paths
from db_schema import run_exists
from runtime_context import get_stryd_path, get_garmin_file


@dataclass
class MenuItem:
    """ Menu item class """
    key: str                 # what the user types: "1", "a", "v", etc.
    label: str               # text shown to the user
    action: Optional[Callable[[], None]] = None  # optional callback


def menu_guard(param_a, *args):
    """ Guard for menus that return None to avoid traceback """
    return (param_a, *args) if param_a else None


def loadcsv_2df(file):
    """ Loads a csv and returns its dataframe """
    file_df = pd.read_csv(file)
    return file_df


def calc_df_to_pace(df: pd.DataFrame, seconds_col : str, meters_col : str) -> pd.Series:
    """ Takes seconds and meters from a dataframe calculates and returns pace """
    elapsed_sec = (df[seconds_col] - df[seconds_col].iloc[0]).dt.total_seconds()
    dist_km = (df[meters_col] - df[meters_col].iloc[0]) / 1000.0
    pace = (elapsed_sec / dist_km.replace(0,np.nan)) / 60
    return pace # min/km


def input_positive_number(prompt: str = "Enter a positive number: ") -> int:
    """ Gets a positive integer from user input """
    while True:
        x = input(prompt).strip()
        try:
            number = int(x)
            if number <= 0:
                print("Please enter a positive integer (e.g., 4).")
                continue
            return number
        except ValueError:
            print("Invalid input. Please enter a whole number (e.g., 4).")


def render_menu(title: str, items: Iterable[MenuItem], footer: str | None = None) -> None:
    """ Menu Display """
    print(f"\n=== {title} ===")
    for it in items:
        print(f"[{it.key}] {it.label}")
    if footer:
        print(footer)


def prompt_menu(title: str, items: list[MenuItem], allow_back: bool = True, allow_quit: bool = True) -> str:
    """ Create the core of the menu """
    # Add "back" , "quit" if missing
    augmented = items.copy()
    if allow_back and not any(i.key.lower() == "b" for i in augmented):
        augmented.append(MenuItem("b", "Back"))
    if allow_quit and not any(i.key.lower() == "q" for i in augmented):
        augmented.append(MenuItem("q", "Quit"))

    valid_keys = {i.key.lower(): i for i in augmented}

    while True:
        render_menu(title, augmented)
        choice = input("> ").strip().lower()
        if choice in valid_keys:
            item = valid_keys[choice]
            if item.action:
                item.action()  # optional: execute and then either return or loop
            return item.key  # return the chosen key so caller decides what to do
        print("⚠️ Invalid choice. Try again.")


def print_table(df, tablefmt=None, floatfmt=".2f",
                numalign="decimal", showindex=False,
                headers="keys", colalign=None):
    """ Takes a dataframe and prints it in table format using tabulate """
    # numeric columns should remain floats for alignment

    tf = tablefmt or "psql"
    if colalign is None:
        print(tabulate(
            df,
            headers=headers,
            tablefmt=tf,
            showindex=showindex,
            floatfmt=floatfmt,
            numalign=numalign,
        ))
    else:
        print(tabulate(
            df,
            headers=headers,
            tablefmt=tf,
            showindex=showindex,
            floatfmt=floatfmt,
            numalign=numalign,
            colalign=list(colalign),  # ensure it's a list
        ))


def get_keys(keys):
    """ Return a list of headers """
    from metrics import METRICS_SPEC
    return [METRICS_SPEC[k]["label"] for k in keys]


def print_list_table(rows, headers):
    """ Takes list of tuples and prints the output """
    if not rows:
        print("⚠️ No results found.")
        return
    print(tabulate(rows, headers=headers, tablefmt="psql", showindex=False, floatfmt=".2f", numalign="decimal"))


def prompt_yes_no(prompt_msg, default=True):
    """ Prompt the user for a yes/no input. Returns True for yes, False for no. """
    # Default determines what happens on empty input.
    while True:
        user_input = input(f"{prompt_msg} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        if not user_input:
            return default
        if user_input in ["y", "yes"]:
            return True
        if user_input in ["n", "no"]:
            return False
        print("⚠️ Invalid input. Please enter Y or N.")


def get_valid_input(prompt, cast_func=int, retries=3, bound_start=None, bound_end=None):
    """ Ask the user for input. Returns the cast value if valid, or None if retries are exhausted. """
    for attempt in range(1, retries + 1):
        try:
            return cast_func(input(prompt))
        except Exception:
            if attempt < retries:
                print("⚠️ Invalid input. Try again.")
            else:
                print("⚠️ Invalid input. Exiting to main menu...")
                return None


def get_paths_with_prompt():
    """ Loads default Stryd/Garmin paths if they exist else prompts for them, returns the paths """
    # Try to load last used paths
    stryd_path = get_stryd_path()
    garmin_path = get_garmin_file()

    if stryd_path and garmin_path:
        print("\n🧠 Last used paths:")
        print(f"📁 STRYD folder:     {stryd_path}")
        print(f"📄 Garmin CSV file:  {garmin_path}")
        if prompt_yes_no("♻️  Reuse these paths?"):
            return stryd_path, garmin_path

    # Manual Stryd folder input
        else:
            stryd_path = Path(input("📂 Enter path to STRYD folder: ").strip())
            if not stryd_path.exists():
                print(f"📁 STRYD folder not found, creating: {stryd_path}")
                stryd_path.mkdir(parents=True, exist_ok=True)

        # Prompt for Garmin file until found or exit
    while True:
        garmin_file = Path(input("📄 Enter path to Garmin CSV file: ").strip())
        if garmin_file.exists():
            save_paths({"STRYD_DIR":stryd_path , "GARMIN_CSV_FILE":garmin_file})
            return stryd_path, garmin_file
        if not prompt_yes_no("❌ Garmin file not found. Try again?"):
            logging.warning("Aborted: Garmin file not provided. Operation cancelled.")
            return None, None
        if not garmin_file.exists():
            print(f"❌ Default Garmin CSV not found at: {garmin_file}")
            # fall through to manual prompt below
        else:
            return stryd_path, garmin_file



def interactive_run_insert(stryd_file, garmin_file, conn, timezone_str=None) -> bool | None:
    """ Loads Stryd/Garmin csv's creates df's from them prompts for timezone calls pipeline,
     checks if there is a match with Garmin csv if not asks to parse witohut match, outputs a report of the tried files """
    from file_parsing import ZeroStrydDataError
    from pipeline import process_csv_pipeline, insert_full_run

    file_name = Path(stryd_file).name

    # Transform Stryd and Garmin csv's to dataframes
    stryd_raw_df = loadcsv_2df(stryd_file)
    garmin_raw_df = loadcsv_2df(garmin_file)

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

        try:
            stryd_df, _, avg_power, _, avg_hr, total_m = process_csv_pipeline(stryd_raw_df, garmin_raw_df, timezone_str, file_name)

            # ✅ Use LOCAL timestamp string to match DB, no UTC conversion here
            start_time = stryd_df["ts_local"].iloc[0]
            start_time_str = start_time.isoformat(sep=' ', timespec='seconds')

            # Check the DB to avoid re-inserts
            if run_exists(conn, start_time_str):
                logging.info(f"⚠️ Already in DB: {file_name} ({start_time_str})")
                return False

        except ZeroStrydDataError as e:
            logging.info(f"⏭️  Skipped: {Path(stryd_file).name} — {e}")
            return False

        except Exception as e:
            logging.error(f"❌ Failed to process {stryd_file}: {e}")
            return False

        workout_name = stryd_df.get("wt_name", pd.Series(["Unknown"])).iloc[0]

        # Garmin matched
        if workout_name != "Unknown":
            insert_full_run(stryd_df, workout_name, notes="",avg_power=avg_power, avg_hr=avg_hr,total_m=total_m, conn=conn)
            logging.info(f"✅ Inserted with Garmin match: {file_name} - {total_m/1000:.2f} km")
            return True

        # Garmin not matched → show menu
        print(f"\n❌ No Garmin match found for {file_name}.")
        x = input(
            "What would you like to do?\n"
            "[1] Parse anyway without Garmin match\n"
            "[2] Try another timezone\n"
            "[3] Skip for now\n"
            "[4] Exit\n> "
        ).strip()

        if x == "1":
            insert_full_run(stryd_df, workout_name, notes="",avg_power=avg_power, avg_hr=None,total_m=total_m, conn=conn)
            logging.info(f"✅ Inserted without Garmin match: {stryd_file}")
            return True

        elif x == "2":
            # force a re-prompt next loop
            timezone_str = None
            continue

        elif x == "3":
            logging.info(f"⏭️ Skipped: {file_name}")
            return False

        elif x == "4":
            logging.info("👋 Exiting early.")
            return None

        else:
            print("❓ Invalid choice. Try again.")