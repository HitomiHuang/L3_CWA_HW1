from __future__ import annotations

import math
from typing import Any

import pandas as pd

from config import TIMEZONE


def number(value: Any) -> float | None:
    if value is None or str(value).strip() in {"", "-", "--", "NaN", "N/A", "X"}:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result <= -90:
        return None
    return result


def taipei_iso(value: Any) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(TIMEZONE)
    else:
        parsed = parsed.tz_convert(TIMEZONE)
    return parsed.isoformat(timespec="seconds")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return None if result in {"", "-99", "-999", "X"} else result
