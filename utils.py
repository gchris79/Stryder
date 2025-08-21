from dataclasses import dataclass
from datetime import datetime, date
from typing import Callable, Iterable, Optional
import pandas as pd
import logging
from zoneinfo import ZoneInfo
from pathlib import Path
import tzlocal
from tabulate import tabulate
from path_memory import load_last_used_paths, save_last_used_paths
from db_schema import run_exists


@dataclass
class MenuItem:
    key: str                 # what the user types: "1", "a", "v", etc.
    label: str               # text shown to the user
    action: Optional[Callable[[], None]] = None  # optional callback



def fmt_seconds_to_hms(total_seconds: int) -> str:
    total_seconds = int(total_seconds or 0)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def fmt_pace(sec_per_km: float | None) -> str:
    if not sec_per_km or sec_per_km <= 0:
        return "-"
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km % 60))
    return f'{m}:{s:02}"/km'


def hms_to_seconds(s: str) -> int:
    parts = s.split(":")
    if len(parts) == 3:
        h, m, sec = map(int, parts)
    elif len(parts) == 2:  # allow MM:SS
        h, m, sec = 0, *map(int, parts)
    else:
        raise ValueError(f"Bad time format: {s!r}")
    return h * 3600 + m * 60 + sec


def input_positive_number(prompt: str = "Enter a positive number: ") -> int:

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


def as_date(d: datetime | date) -> date:
    return d.date() if isinstance(d, datetime) else d


def string_to_datetime(date_str:str) -> datetime:

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError (f"❌ Invalid date format: {date_str}")


def weekly_table_fmt(weekly:pd.DataFrame) -> pd.DataFrame:
    """Format weekly report table datetime fields to strings"""
    out = weekly.copy()
    # Loop to ensure that pandas will not traceback when given 1 week for input
    for col in ("week_start", "week_end"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")

    out["Week Start"] = out["week_start"].dt.strftime("%Y-%m-%d")
    out["Week End"] = out["week_end"].dt.strftime("%Y-%m-%d")
    return out[["Week Start", "Week End","Runs","Distance (km)","Duration","Avg Power", "Avg HR"]]


def print_table(df, tablefmt=None, floatfmt=".2f",
                numalign="decimal", showindex=False,
                headers="keys", colalign=None):
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


def resolve_tz(timezone_str: str | None) -> ZoneInfo:
    return ZoneInfo(timezone_str) if timezone_str else ZoneInfo(tzlocal.get_localzone_name())


def prompt_yes_no(prompt_msg, default=True):
    # Prompt the user for a yes/no input. Returns True for yes, False for no.
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


def get_default_timezone() -> str | None:
    """Read stored timezone (no prompts)."""
    _, _, tz = load_last_used_paths()
    return tz


def ensure_default_timezone() -> str | None:
    """Return stored tz if present; otherwise prompt once, validate, store, and return it."""
    tz = get_default_timezone()
    if tz:
        return tz
    while True:
        entered = input("🌍 Default timezone (e.g., Europe/Athens): ").strip()
        if not entered or entered.lower() == "exit":
            return None
        try:
            # validate
            _ = ZoneInfo(entered)
            save_last_used_paths(timezone=entered)
            return entered
        except Exception:
            print("❌ Unknown timezone. Try again (e.g., Europe/Athens).")


def prompt_for_timezone(file_name=None):
    example = "e.g. Europe/Athens"
    file_msg = f" for {file_name}" if file_name else ""
    tz_str = input(f"🌍 Timezone ({example}){file_msg} (or 'exit' to quit): ").strip()

    if tz_str.lower() in {"exit", "quit", "q"}:
        return "EXIT"

    try:
        ZoneInfo(tz_str)
        return tz_str
    except Exception:
        print("❌ Invalid timezone. Skipping.")
        return None


def get_paths_with_prompt():

    # Try to load last used paths
    stryd_path, garmin_path, _ = load_last_used_paths()
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
            save_last_used_paths(stryd_path, garmin_file)
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
    from file_parsing import ZeroStrydDataError
    from pipeline import process_csv_pipeline, insert_full_run
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

        try:
            stryd_df, _, avg_power, _, avg_hr, total_m = process_csv_pipeline(stryd_file, garmin_file, timezone_str)


            # ✅ Use LOCAL timestamp string to match DB, no UTC conversion here
            start_time = stryd_df["Local Timestamp"].iloc[0]
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

        workout_name = stryd_df.get("Workout Name", pd.Series(["Unknown"])).iloc[0]

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