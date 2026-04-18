from pathlib import Path
from stryder_core.date_utilities import resolve_tz
from stryder_core.profile_memory import get_active_timezone
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
    if expect == "file_or_dir" and not (p.is_file() or p.is_dir()):
        return False
    return True


def core_resolve_timezone(tz_str: str):
    """Pure, no prompts."""
    # if not tz_str:
    #     return None, None
    tzinfo = resolve_tz(tz_str)
    return tz_str, tzinfo


def bootstrap_context_core(data: dict) -> None:
    """
    Pure bootstrap:
    - resolve timezone (no prompts)
    - set runtime_context
    """

    tz_str = get_active_timezone(data)
    tz_str, tzinfo = core_resolve_timezone(tz_str)

    set_context(
        tz_str=tz_str,
        tzinfo=tzinfo
    )