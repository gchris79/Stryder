import json
from pathlib import Path


def save_last_used_paths(stryd_path, garmin_file, file_path="last_used_paths.json"):
    data = {
        "stryd_path": str(stryd_path),
        "garmin_file": str(garmin_file)
    }
    with open(file_path, "w") as f:
        json.dump(data, f)


def load_last_used_paths(file_path="last_used_paths.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return Path(data["stryd_path"]), Path(data["garmin_file"])
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None, None