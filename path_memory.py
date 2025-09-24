import json
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
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_json(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def prompt_valid_path(prompt: str, expect: str) -> Path:
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


def save_paths(updates: dict[str, Path | str]) -> None:
    """Canonical writer for STRYD_DIR / GARMIN_CSV_FILE / TIMEZONE."""
    data = load_json(CONFIG_PATH)
    for k, v in updates.items():
        if isinstance(v, Path):
            data[k] = v.expanduser().as_posix()
        else:
            data[k] = v
    save_json(CONFIG_PATH, data)


def get_saved_timezone() -> str | None:
    return load_json(CONFIG_PATH).get("TIMEZONE")


def set_saved_timezone(tz: str) -> None:
    save_paths({"TIMEZONE": tz})
