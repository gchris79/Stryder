import json
import logging
import os
from pathlib import Path


def resolve_config_path() -> Path:
    """
    Search order (read):
    1) STRYDER_CONFIG env var (if set)
    2) Project-local file next to this module
    3) Per-user file (~/.stryder/last_used_paths.json)

    Write default:
    - If env var set -> write there
    - Else -> project-local file
    """
    env = os.getenv("STRYDER_CONFIG")
    if env:
        return Path(env).expanduser().resolve()

    project_local = Path(__file__).resolve().parent / "last_used_paths.json"
    if project_local.exists():
        return project_local

    user_conf = Path.home() / ".stryder" / "last_used_paths.json"
    if user_conf.exists():
        return user_conf

    # default new writes go project-local (discoverable for users)
    return project_local

CONFIG_PATH = resolve_config_path()

REQUIRED_PATHS = {
    "GARMIN_CSV_FILE": "file",
    "STRYD_DIR": "dir",
}


def load_json(p: Path) -> dict:
    """ Loads json if it's not valid it opens as empty dict """
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logging.warning(f"⚠️ Could not parse {p}. Using empty defaults.")
        return {}
    return data if isinstance(data, dict) else {}


def save_json(p: Path, data: dict):
    """Safely save dict to JSON using atomic write and folder creation."""
    p.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: write to a temporary file
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Step 2: atomically replace the old file
    tmp.replace(p)


def save_paths(updates: dict[str, Path | str]) -> None:
    """ Canonical writer for STRYD_DIR / GARMIN_CSV_FILE / TIMEZONE """
    data = load_json(CONFIG_PATH)
    for k, v in updates.items():
        if isinstance(v, Path):
            data[k] = v.expanduser().as_posix()
        else:
            data[k] = v
    save_json(CONFIG_PATH, data)


def get_saved_timezone() -> str | None:
    """ Gets timezone from json file """
    return load_json(CONFIG_PATH).get("TIMEZONE")


def set_saved_timezone(tz: str) -> None:
    """ Saves the timezone in json file with json format """
    save_paths({"TIMEZONE": tz})
