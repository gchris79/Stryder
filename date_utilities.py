import logging
from datetime import datetime, timezone, date, tzinfo
from typing import Any, Optional, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tzlocal

from path_memory import load_last_used_paths


def to_utc(target: Any, *, in_tz=None,  fold: int | None = None) -> datetime:
    """Parse many time-like inputs and return an aware UTC datetime.

    Supports: datetime (naive/aware), date, int/float (unix s/ms),
              str (unix, ISO8601 incl. 'Z', or '%Y-%m-%d %H:%M:%S%z' /
                  '%Y-%m-%d %H:%M:%S' / '%Y-%m-%d'),
              pandas.Timestamp. """

    dt: Optional[datetime] = None

    if isinstance(target, datetime):                        # Datetime (check code at the end it turns to UTC)
        dt = target

    elif isinstance(target, date):                          # Date to datetime (code at the end turns it to UTC)
        dt = datetime.combine(target, datetime.min.time())

    elif isinstance(target, (int, float)):                  # Unix numeric to UTC
        secs = float(target)
        if secs > 1e12:  # heuristic: treat as milliseconds
            secs /= 1000.0
        return datetime.fromtimestamp(secs, tz=timezone.utc)

    elif isinstance(target, str):
        try:                                                # Unix string to UTC
            secs = float(target)
            if secs > 1e12:
                secs /= 1000.0
            return datetime.fromtimestamp(secs, tz=timezone.utc)
        except ValueError:
            pass
        try:                                                # ISO8601 (support 'Z') to UTC
            dt = datetime.fromisoformat(target.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S%z",              # various datetime/date strings to UTC
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(target, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"❌ Invalid date string: {target!r}")

    else:
        try:                                               # Pandas timestamp to UTC
            import pandas as pd
            if isinstance(target, pd.Timestamp):
                dt = target.to_pydatetime()
        except Exception:
            pass

    if dt is None:
        raise TypeError(f"❌ Unsupported input type: {type(target)!r}")

    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:     # localize if naive, then normalize to UTC
        dt = dt.replace(tzinfo=(in_tz or timezone.utc))     # attach, no clock shift
    return dt.astimezone(timezone.utc)                   # normalize


OutFmt = Literal["iso", "ymd_hmsz", "ymd_hms" ,"ymd"]

def as_aware(dt: datetime, tz=None) -> datetime:
    """ Return aware datetime if no tz default to UTC """
    return dt.astimezone(tz or timezone.utc)


def as_naive(dt: datetime, tz=None) -> datetime:
    """ Return naive datetime """
    return dt.astimezone(tz or timezone.utc).replace(tzinfo=None)


def as_unix(dt: datetime) -> float:
    """ Return Unix datetime """
    return dt.timestamp()


def as_local_date(dt: datetime, tz: tzinfo) -> date:
    """ Return date only aware to target tz """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)
    return dt.date()


def dt_to_string(dt: datetime, fmt: OutFmt = "iso", tz=None) -> str:
    """ Return string datetime on different formats """
    zdt = dt.astimezone(tz or timezone.utc)
    if fmt == "iso":
        return zdt.isoformat()
    if fmt == "ymd_hmsz":
        return zdt.strftime("%Y-%m-%d %H:%M:%S%z")
    if fmt == "ymd_hms":
        return zdt.strftime("%Y-%m-%d %H:%M:%S")
    if fmt == "ymd":
        return zdt.strftime("%Y-%m-%d")
    raise ValueError(f"Unsupported fmt: {fmt}")


def resolve_tz(timezone_str) -> ZoneInfo:
    """ Takes a timezone string e.g "Europe/Athens" and returns a ZoneInfo object. """
    try:
        return ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        logging.warning(f"⚠️ Unknown timezone '{timezone_str}', falling back to system local.")
    return ZoneInfo(tzlocal.get_localzone_name())


def runtime.get_tzinfo()
