from __future__ import annotations

from datetime import datetime
from typing import Any

from services.parse_utils import number as _number, taipei_iso as _taipei_iso

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


def validate_forecast_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check time ranges and temperatures without adding runtime dependencies."""
    invalid_time = reversed_range = invalid_temps = 0
    for row in rows:
        try:
            start = datetime.fromisoformat(row["start_time"])
            end = datetime.fromisoformat(row["end_time"])
        except (KeyError, TypeError, ValueError):
            invalid_time += 1
            continue
        if end <= start:
            reversed_range += 1
        low, high = row.get("min_temp"), row.get("max_temp")
        if low is not None and high is not None and low > high:
            invalid_temps += 1
    if invalid_time:
        raise ValueError(f"有 {invalid_time} 筆預報的有效時間格式錯誤。")
    if reversed_range:
        raise ValueError(f"有 {reversed_range} 筆預報的結束時間不晚於開始時間。")
    if invalid_temps:
        raise ValueError(f"有 {invalid_temps} 筆資料的最低溫高於最高溫。")
    return rows
