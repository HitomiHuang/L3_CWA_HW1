from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

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
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip().replace("/", "-").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    taipei = ZoneInfo(TIMEZONE)
    parsed = parsed.replace(tzinfo=taipei) if parsed.tzinfo is None else parsed.astimezone(taipei)
    return parsed.isoformat(timespec="seconds")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return None if result in {"", "-99", "-999", "X"} else result
