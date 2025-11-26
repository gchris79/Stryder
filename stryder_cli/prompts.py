from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from stryder_core.date_utilities import tzinfo_or_none, to_utc


def prompt_valid_path(prompt: str, expect: str) -> Path:
    """ Prompts user for a valid path """
    while True:
        val = input(prompt).strip()
        if not val:
            print("⚠️ Required path not provided, try again.")
            continue
        p = Path(val).expanduser()
        if expect == "file":
            if p.is_file():
                return p
            print("⚠️ Not a valid file, try again.")
        elif expect == "dir":
            if p.exists() and p.is_dir():
                return p
            # match old behavior: create it if missing
            try:
                p.mkdir(parents=True, exist_ok=True)
                return p
            except Exception as e:
                print(f"⚠️ Could not create directory ({e}). Try again.")
        else:
            # Fallback—shouldn't happen with our REQUIRED_PATHS
            if p.exists():
                return p
            print("⚠️ Path does not exist, try again.")


def prompt_for_timezone(file_name=None):
    """ Prompt user for timezone """
    example = "e.g. Europe/Athens"
    file_msg = f" for {file_name}" if file_name else ""
    tz_str = input(f"🌍 Timezone ({example}){file_msg} (or 'exit' to quit): ").strip()

    if tz_str.lower() in {"exit", "quit", "q"}:
        return "EXIT"

    try:
        ZoneInfo(tz_str)
        return tz_str
    except ZoneInfoNotFoundError:
        print("❌ Invalid timezone. Skipping.")
        return None


def input_date(prompt: str) -> datetime:
    """ Takes user input date, combines it with last saved input and convert it to UTC """
    tz = tzinfo_or_none()       # fetch last saved timezone
    while True:
        raw = input(prompt).strip()
        try:
            # validate format first
            dt = datetime.strptime(raw, "%Y-%m-%d")
            # then convert to UTC using your helper
            return to_utc(dt, in_tz=tz)
        except ValueError:
            print("⚠️ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-09-24).")


def ensure_default_timezone() -> str | None:
    """Return stored tz if present; otherwise prompt once, validate, store, and return it."""
    from stryder_core.path_memory import get_saved_timezone, set_saved_timezone
    tz = get_saved_timezone()
    if tz:
        return tz
    while True:
        entered = input("🌍 Default timezone (e.g., Europe/Athens): ").strip()
        if not entered or entered.lower() == "exit":
            return None
        try:
            # validate
            _ = ZoneInfo(entered)
            set_saved_timezone(entered)
            return entered
        except ZoneInfoNotFoundError:
            print("❌ Unknown timezone. Try again (e.g., Europe/Athens).")


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
