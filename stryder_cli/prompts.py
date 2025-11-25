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
