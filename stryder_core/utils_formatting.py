import math
from typing import Literal

""" fmt_pace is the core function and fmt_pace_km and fmt_pace_no_unit wrapper functions for picking the mode """
def fmt_pace_km(seconds, pos=None):
    # ----- DON'T ERASE THE "pos=None" it's used by the formatter later ------ #
    return fmt_pace(seconds, with_unit=True)

def fmt_pace_no_unit(seconds, pos=True):
    # ----- DON'T ERASE THE "pos=None" it's used by the formatter later ------ #
    return fmt_pace(seconds, with_unit=False)

def fmt_pace(seconds: float | int | None, with_unit: bool = False) -> str:
    """ Takes seconds and returns pace in mm/ss or mm/ss/km format """
    # Validate input
    try:
        sec = float(seconds)
    except (TypeError, ValueError):
        return ""
    if not math.isfinite(sec) or sec <= 0:
        return ""
    # Convert and format
    sec = int(round(sec))
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}" if not with_unit else f"{m}:{s:02d}/km"


def fmt_str_decimals(fl_num) -> str:
    """ Format string decimal numbers, returns formatted string """
    fmt_num = "{:.2f}".format(fl_num)
    return fmt_num


def fmt_distance(meters) -> float:
    """ Calculates km from meters """
    km = float(meters / 1000)
    return km


def fmt_distance_km_str(meters) -> str:
    """ Takes distance in meters and returns string formatted km """
    km = fmt_distance(meters)
    return fmt_str_decimals(km)

""" format_seconds is the core function and fmt_hms and fmt_hm wrapper functions for picking the mode """
def fmt_hms(seconds, pos=None):
    # ----- DON'T ERASE THE "pos=None" its used by the formatter later ------ #
    return format_seconds(seconds,'hms')

def fmt_hm(seconds, pos=None):
    # ----- DON'T ERASE THE "pos=None" its used by the formatter later ------ #
    return format_seconds(seconds,'hm')

def format_seconds(
    seconds,
    mode:Literal["hms","hm"] = "hm",
):
    """ Takes seconds and returns time in hms or hm format """
    # Check for undesirable values normalizing to 0
    try:
        total_sec = float(seconds)
    except (TypeError, ValueError):
        total_sec = 0
    if math.isnan(total_sec):
        total_sec = 0
    if total_sec < 0:
        total_sec = 0
    # Round to nearest second
    sec = max(0, int(round(total_sec)))

    # Format to time
    h, rem = divmod(sec, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02}:{m:02}" if mode == "hm" else f"{h:02}:{m:02}:{s:02}"