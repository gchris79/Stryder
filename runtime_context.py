from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

# internal cache (module-level “private” variables)
_tz_str: Optional[str] = None
_tzinfo: Optional[ZoneInfo] = None
_stryd_path: Optional[Path] = None
_garmin_file: Optional[Path] = None
_exports_dir: Optional[Path] = None

def set_context(
    tz_str: str,
    tzinfo: ZoneInfo,
    stryd_path: Optional[Path] = None,
    garmin_file: Optional[Path] = None,
    exports_dir: Optional[Path] = None,
) -> None:
    """Store session values once after bootstrap."""
    global _tz_str, _tzinfo, _stryd_path, _garmin_file, _exports_dir
    _tz_str = tz_str
    _tzinfo = tzinfo
    _stryd_path = stryd_path
    _garmin_file = garmin_file
    _exports_dir = exports_dir


def get_tzinfo() -> ZoneInfo:
    if _tzinfo is None:
        raise RuntimeError("runtime_context not initialized: call set_context() first")
    return _tzinfo


def get_tz_str() -> str:
    if _tz_str is None:
        raise RuntimeError("runtime_context not initialized: call set_context() first")
    return _tz_str


def get_stryd_path() -> Path:
    if _stryd_path is None:
        raise RuntimeError("runtime_context not initialized: call set_context() first")
    return _stryd_path


def get_garmin_file() -> Path:
    if _garmin_file is None:
        raise RuntimeError("runtime_context not initialized: call set_context() first")
    return _garmin_file