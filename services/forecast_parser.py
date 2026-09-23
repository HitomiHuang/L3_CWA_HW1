from __future__ import annotations

from typing import Any

import pandas as pd

from config import TIMEZONE

ELEMENTS = {"Wx", "MinT", "MaxT", "PoP", "CI"}


def _value_from_parameter(parameter: dict[str, Any] | None, element_name: str) -> Any:
    if not parameter:
        return None
    name, value = parameter.get("parameterName"), parameter.get("parameterValue")
    if element_name == "Wx":
        return name if name not in (None, "") else value
    if element_name in {"MinT", "MaxT", "PoP"}:
        return value if value not in (None, "") else name
    return name if name not in (None, "") else value


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() in {"", "-", "--", "NaN", "N/A"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _taipei_iso(value: Any) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(TIMEZONE)
    else:
        parsed = parsed.tz_convert(TIMEZONE)
    return parsed.isoformat(timespec="seconds")


def parse_36_hour_forecast(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Normalize CWA REST JSON by matching every element on its valid time range."""
    records = payload.get("records") or {}
    dataset_info = records.get("datasetInfo") or records.get("DatasetInfo") or {}
    issue_time = _taipei_iso(dataset_info.get("issueTime") or dataset_info.get("IssueTime"))
    source_updated = _taipei_iso(
        dataset_info.get("updateTime") or dataset_info.get("update") or dataset_info.get("UpdateTime") or payload.get("sent")
    )
    output: list[dict[str, Any]] = []
    for location in records.get("location", []) or []:
        location_name = location.get("locationName") or location.get("LocationName")
        if not location_name:
            continue
        periods: dict[tuple[str, str], dict[str, Any]] = {}
        for element in location.get("weatherElement", []) or []:
            element_name = element.get("elementName") or element.get("ElementName")
            if element_name not in ELEMENTS:
                continue
            for period in element.get("time", []) or []:
                start_time = _taipei_iso(period.get("startTime") or period.get("StartTime"))
                end_time = _taipei_iso(period.get("endTime") or period.get("EndTime"))
                if not start_time or not end_time:
                    continue
                key = (start_time, end_time)
                row = periods.setdefault(key, {
                    "location": str(location_name), "start_time": start_time, "end_time": end_time,
                    "wx": None, "weather_code": None, "min_temp": None, "max_temp": None,
                    "pop": None, "comfort": None,
                })
                parameter = period.get("parameter") or period.get("Parameter") or {}
                value = _value_from_parameter(parameter, element_name)
                if element_name == "Wx":
                    row["wx"] = str(value) if value not in (None, "") else None
                    row["weather_code"] = str(parameter.get("parameterValue") or "") or None
                elif element_name == "MinT":
                    row["min_temp"] = _number(value)
                elif element_name == "MaxT":
                    row["max_temp"] = _number(value)
                elif element_name == "PoP":
                    row["pop"] = _number(value)
                elif element_name == "CI":
                    row["comfort"] = str(value) if value not in (None, "") else None
        output.extend(periods.values())
    output.sort(key=lambda row: (row["location"], row["start_time"], row["end_time"]))
    if not output:
        raise ValueError("無法從 API 回傳內容解析出有效的預報時段。")
    return output, issue_time, source_updated


def validate_forecast_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Return a DataFrame for quality checks while leaving sparse values intact."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="coerce")
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="coerce")
    invalid = frame["start_time"].isna() | frame["end_time"].isna()
    if invalid.any():
        raise ValueError(f"有 {int(invalid.sum())} 筆預報的有效時間格式錯誤。")
    reversed_ranges = frame["end_time"] <= frame["start_time"]
    if reversed_ranges.any():
        raise ValueError(f"有 {int(reversed_ranges.sum())} 筆預報的結束時間不晚於開始時間。")
    invalid_temps = frame["min_temp"].notna() & frame["max_temp"].notna() & (frame["min_temp"] > frame["max_temp"])
    if invalid_temps.any():
        raise ValueError(f"有 {int(invalid_temps.sum())} 筆資料的最低溫高於最高溫。")
    return frame
