from __future__ import annotations

from typing import Any

from services.parse_utils import clean_text, number, taipei_iso


ELEMENT_FIELDS = {
    "最高溫度": ("max_temp", "MaxTemperature"),
    "最低溫度": ("min_temp", "MinTemperature"),
    "平均相對濕度": ("relative_humidity", "RelativeHumidity"),
    "12小時降雨機率": ("pop", "ProbabilityOfPrecipitation"),
    "天氣現象": ("wx", "Weather"),
    "天氣預報綜合描述": ("description", "WeatherDescription"),
}


def _element_values(period: dict[str, Any]) -> dict[str, Any]:
    values = period.get("ElementValue") or period.get("elementValue") or []
    if isinstance(values, dict):
        return values
    return values[0] if values and isinstance(values[0], dict) else {}


def parse_weekly_forecast(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """Parse CWA F-D0047-091 (22 county/city locations, 12-hour periods)."""
    records = payload.get("records") or {}
    wrappers = records.get("Locations") or records.get("locations") or []
    locations: list[dict[str, Any]] = []
    for wrapper in wrappers:
        group = wrapper.get("Location") or wrapper.get("location") or []
        if isinstance(group, list):
            locations.extend(group)

    rows_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for location in locations:
        location_name = clean_text(location.get("LocationName") or location.get("locationName"))
        if not location_name:
            continue
        elements = location.get("WeatherElement") or location.get("weatherElement") or []
        for element in elements:
            element_name = clean_text(element.get("ElementName") or element.get("elementName"))
            mapped = ELEMENT_FIELDS.get(element_name or "")
            if not mapped:
                continue
            field, value_key = mapped
            for period in element.get("Time") or element.get("time") or []:
                start = taipei_iso(period.get("StartTime") or period.get("startTime"))
                end = taipei_iso(period.get("EndTime") or period.get("endTime"))
                if not start or not end:
                    continue
                key = (location_name, start, end)
                row = rows_by_key.setdefault(key, {
                    "location": location_name, "start_time": start, "end_time": end,
                    "wx": None, "description": None, "min_temp": None, "max_temp": None,
                    "pop": None, "relative_humidity": None,
                })
                value = _element_values(period).get(value_key)
                if field in {"wx", "description"}:
                    row[field] = clean_text(value)
                else:
                    row[field] = number(value)

    rows = sorted(rows_by_key.values(), key=lambda row: (row["location"], row["start_time"], row["end_time"]))
    if not rows:
        raise ValueError("無法從一週預報回應解析出有效時段。")
    return rows, None, taipei_iso(payload.get("sent") or payload.get("Sent"))
