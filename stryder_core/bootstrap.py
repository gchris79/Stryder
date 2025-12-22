from pathlib import Path
from stryder_core.date_utilities import resolve_tz
from stryder_core.path_memory import REQUIRED_PATHS
from stryder_core.runtime_context import set_context


def validate_path(p: Path | None, expect: str) -> bool:
    """ Check whether a path is valid. """
    if p is None:
        return False
    if not p.exists():
        return False
    if expect == "file" and not p.is_file():
        return False
    if expect == "dir" and not p.is_dir():
        return False
    return True


def bootstrap_defaults_core(data: dict) -> dict[str, Path]:
    """
    - reads defaults from data
    - validates paths WITHOUT prompting
    - DOES NOT print anything
    - returns whatever is valid, leaves invalid ones as None
    """
    resolved = {}

    for key, expect in REQUIRED_PATHS.items():
        raw = data.get(key)
        p = Path(raw).expanduser() if raw else None

        if validate_path(p, expect):
            resolved[key] = p
        else:
            resolved[key] = None   # not resolved yet

    return resolved


def core_resolve_timezone(tz_str: str | None):
    """Pure, no prompts."""
    if not tz_str:
        return None, None
    tzinfo = resolve_tz(tz_str)
    return tz_str, tzinfo


def bootstrap_context_core(data: dict) -> dict[str, Path]:
    """
    Pure bootstrap:
    - validate paths (no prompts)
    - resolve timezone (no prompts)
    - set runtime_context
    - return resolved values
    """
    resolved_paths = bootstrap_defaults_core(data)

    tz_str = data.get("TIMEZONE")
    tz_str, tzinfo = core_resolve_timezone(tz_str)

    set_context(
        tz_str=tz_str,
        tzinfo=tzinfo,
        stryd_path=resolved_paths.get("STRYD_DIR"),
        garmin_file=resolved_paths.get("GARMIN_CSV_FILE"),
    )

    return resolved_paths