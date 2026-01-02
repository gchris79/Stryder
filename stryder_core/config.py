from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # goes from stryder_core/ up to project root
DB_PATH = BASE_DIR / "runs_data.db"

COMMON_TIMEZONES = [
    "UTC",
    "Europe/Athens",
    "Europe/Berlin",
    "Europe/London",
    "Europe/Paris",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Europe/Zurich",
    "Europe/Stockholm",
    "America/New_York",
    "America/Chicago",
    "America/Los_Angeles",
    "America/Denver",
    "Asia/Tokyo",
    "Australia/Sydney",
]