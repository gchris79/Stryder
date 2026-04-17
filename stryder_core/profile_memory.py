import json
import logging
import os
from pathlib import Path

from stryder_core.config import COMMON_TIMEZONES


def resolve_config_path() -> Path:
    """
    Search order (read):
    1) STRYDER_CONFIG env var (if set)
    2) Project-local file next to this module
    3) Per-user file (~/.stryder/profiles.json)

    Write default:
    - If env var set -> write there
    - Else -> project-local file
    """
    env = os.getenv("STRYDER_CONFIG")
    if env:
        return Path(env).expanduser().resolve()

    project_local = Path(__file__).resolve().parent / "profiles.json"
    if project_local.exists():
        return project_local

    user_conf = Path.home() / ".stryder" / "profiles.json"
    if user_conf.exists():
        return user_conf

    # default new writes go project-local (discoverable for users)
    return project_local

CONFIG_PATH = resolve_config_path()

REQUIRED_PATHS = {
    "garmin_csv_file": "file",
    "stryd_dir": "dir",
}


def blank_profile_config() -> dict:
    """ Creates a blank profile dict """
    return {
        "active_profile": None,
        "profiles": {},
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


def check_boot_json(data: dict) -> str:
        """ Check the imported json's fields and returns status. """
        if not (
            "active_profile" in data
            and "profiles" in data
            and isinstance(data["active_profile"], str)
        ):
            return "invalid"

        active_profile = data["active_profile"]

        if not isinstance(data["profiles"], dict):
            return "invalid"

        if active_profile not in data["profiles"]:
            return "invalid"

        profile = data["profiles"][active_profile]

        if not isinstance(profile, dict):
            return "invalid"

        if "timezone" not in profile:
            return "needs_setup"

        tz = profile["timezone"]

        if not isinstance(tz, str):
            return "needs_setup"

        if tz not in COMMON_TIMEZONES:
            return "needs_setup"

        return "valid"

def save_paths(updates: dict[str, Path | str]) -> None:
    """ Canonical writer for stryd_dir / garmin_csv_file / timezone """
    data = load_json(CONFIG_PATH)
    for k, v in updates.items():
        if isinstance(v, Path):
            data[k] = v.expanduser().as_posix()
        else:
            data[k] = v
    save_json(CONFIG_PATH, data)


def get_saved_timezone() -> str | None:
    # TODO Used only from CLI will be deprecated
    """ Gets timezone from json file """
    return load_json(CONFIG_PATH).get("TIMEZONE")


def set_saved_timezone(tz: str) -> None:
    # TODO Used only from CLI will be deprecated
    """ Saves the timezone in json file with json format """
    save_paths({"TIMEZONE": tz})


def get_active_profile(data: dict) -> str:
    """ Returns the active profile from json / use after json is valitation """
    return data["active_profile"]


def get_active_profile_dict(data: dict) -> dict:
    """ Returns the inner profile dict / use after json is valitation """
    return data["profiles"][get_active_profile(data)]


def get_active_timezone(data: dict) -> str:
    """ Returns timezone from active profile / use after json is valitation """
    return get_active_profile_dict(data)["timezone"]


def get_active_stryd_path(data:dict):
    """ Returns stryd path from active profile / use after json is valitation """
    return get_active_profile_dict(data)["stryd_dir"]


def get_active_garmin_csv(data:dict):
    """ Returns garmin path from active profile / use after json is valitation """
    return get_active_profile_dict(data)["garmin_csv_file"]


def set_active_profile(data:dict, active_profile:str):
    """ Set the active profile """
    data["active_profile"] = active_profile


def create_profile(data:dict, profile_name:str):
    """ Create a profile blank dict """
    data["profiles"][profile_name] = {
        "timezone": None,
        "stryd_dir": None,
        "garmin_csv_file": None,
        "weight": None,
    }
    set_active_profile(data, profile_name)
    

def set_active_timezone(data:dict, tz:str|None):
    """ Set profile's timezone """
    get_active_profile_dict(data)["timezone"] = tz


def set_active_stryd_path(data:dict, stryd_path:str|None):
    """ Set profile's stryd path """
    get_active_profile_dict(data)["stryd_dir"] = stryd_path


def set_active_garmin_csv(data:dict, garmin_path:str|None):
    """ Saves profile's garmin path """
    get_active_profile_dict(data)["garmin_csv_file"] = garmin_path
