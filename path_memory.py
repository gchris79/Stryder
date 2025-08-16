import json
from pathlib import Path


LAST_USED_PATHS_FILE = Path("last_used_paths.json")


def save_last_used_paths(stryd_path=None, garmin_file=None, timezone=None, file_path=LAST_USED_PATHS_FILE):
    """Merge-and-save last-used paths + timezone (backward compatible)."""
    data = {}
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}

    if stryd_path is not None:
        data["stryd_path"] = str(stryd_path)
    if garmin_file is not None:
        data["garmin_file"] = str(garmin_file)
    if timezone is not None:
        data["timezone"] = timezone

    Path(file_path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_last_used_paths(file_path=LAST_USED_PATHS_FILE):
    """Return (stryd_path|None, garmin_file|None, timezone|None). Accepts legacy keys too."""
    if not Path(file_path).exists():
        return None, None, None
    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8")) or {}
    except Exception:
        return None, None, None

    # accept legacy uppercase keys
    stryd = data.get("stryd_path") or data.get("STRYD_FOLDER")
    garmin = data.get("garmin_file") or data.get("GARMIN_CSV_FILE")
    tz     = data.get("timezone")   or data.get("TIMEZONE")

    return (Path(stryd) if stryd else None,
            Path(garmin) if garmin else None,
            tz if tz else None)
