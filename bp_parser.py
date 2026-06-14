"""Parse blood-pressure readings from free-form chat text.

Returns a dict ``{"systolic": int, "diastolic": int, "pulse": int | None}``
when a plausible reading is found, otherwise ``None``.
"""
import re
from typing import Optional, TypedDict


class BPReading(TypedDict):
    systolic: int
    diastolic: int
    pulse: Optional[int]


# Plausible physiological ranges for home measurement.
SYSTOLIC_MIN, SYSTOLIC_MAX = 50, 300
DIASTOLIC_MIN, DIASTOLIC_MAX = 30, 200
PULSE_MIN, PULSE_MAX = 30, 200

# systolic/diastolic optionally followed by a pulse, separated by / or spaces.
_SLASH_RE = re.compile(
    r"(?<!\d)(\d{2,3})\s*[/／]\s*(\d{2,3})(?:\s*[/／]\s*(\d{2,3}))?"
)
# Labelled form: 收縮壓120 舒張壓80 脈搏70 / 高壓 / 低壓
_LABEL_SYS = re.compile(r"(?:收縮壓|高壓|systolic)\s*[:：]?\s*(\d{2,3})")
_LABEL_DIA = re.compile(r"(?:舒張壓|低壓|diastolic)\s*[:：]?\s*(\d{2,3})")
_LABEL_PULSE = re.compile(r"(?:脈搏|心跳|脈率|pulse|hr)\s*[:：]?\s*(\d{2,3})")
# Three (or two) bare numbers separated by whitespace.
_TRIPLE_RE = re.compile(r"(?<!\d)(\d{2,3})\s+(\d{2,3})(?:\s+(\d{2,3}))?(?!\d)")


def _valid_bp(systolic: int, diastolic: int) -> bool:
    return (
        SYSTOLIC_MIN <= systolic <= SYSTOLIC_MAX
        and DIASTOLIC_MIN <= diastolic <= DIASTOLIC_MAX
        and systolic > diastolic
    )


def _clean_pulse(pulse: Optional[int]) -> Optional[int]:
    if pulse is None:
        return None
    return pulse if PULSE_MIN <= pulse <= PULSE_MAX else None


def _build(systolic: int, diastolic: int, pulse: Optional[int]) -> Optional[BPReading]:
    if not _valid_bp(systolic, diastolic):
        return None
    return {"systolic": systolic, "diastolic": diastolic, "pulse": _clean_pulse(pulse)}


def parse_bp(text: str) -> Optional[BPReading]:
    if not text:
        return None

    # 1. Labelled form takes priority (most explicit).
    sys_m = _LABEL_SYS.search(text)
    dia_m = _LABEL_DIA.search(text)
    if sys_m and dia_m:
        pulse_m = _LABEL_PULSE.search(text)
        result = _build(
            int(sys_m.group(1)),
            int(dia_m.group(1)),
            int(pulse_m.group(1)) if pulse_m else None,
        )
        if result:
            return result

    # 2. Slash form: 120/80 or 120/80/70 (also picks up labelled pulse if present).
    slash_m = _SLASH_RE.search(text)
    if slash_m:
        pulse = int(slash_m.group(3)) if slash_m.group(3) else None
        if pulse is None:
            pulse_m = _LABEL_PULSE.search(text)
            pulse = int(pulse_m.group(1)) if pulse_m else None
        result = _build(int(slash_m.group(1)), int(slash_m.group(2)), pulse)
        if result:
            return result

    # 3. Two or three bare numbers separated by whitespace.
    triple_m = _TRIPLE_RE.search(text)
    if triple_m:
        pulse = int(triple_m.group(3)) if triple_m.group(3) else None
        result = _build(int(triple_m.group(1)), int(triple_m.group(2)), pulse)
        if result:
            return result

    return None
