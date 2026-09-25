"""Normalize the CWA W-C0034-005 tropical cyclone XML for the public map."""

from __future__ import annotations

from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from services.parse_utils import number, taipei_iso


def _text(parent: ET.Element, name: str) -> str | None:
    node = parent.find(f"{{*}}{name}")
    return node.text.strip() if node is not None and node.text else None


def _position(fix: ET.Element, forecast: bool = False) -> dict | None:
    latitude = number(_text(fix, "CoordinateLatitude"))
    longitude = number(_text(fix, "CoordinateLongitude"))
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if forecast:
        initial = taipei_iso(_text(fix, "InitialTime"))
        hours = number(_text(fix, "ForecastHour"))
        if not initial or hours is None:
            return None
        valid_at = (datetime.fromisoformat(initial) + timedelta(hours=hours)).isoformat(timespec="seconds")
    else:
        valid_at = taipei_iso(_text(fix, "DateTime"))
    if not valid_at:
        return None
    return {
        "time": valid_at,
        "latitude": latitude,
        "longitude": longitude,
        "wind_speed": number(_text(fix, "MaxWindSpeed")),
        "pressure": number(_text(fix, "Pressure")),
    }


def parse_typhoon_xml(payload: bytes) -> tuple[list[dict], str | None]:
    root = ET.fromstring(payload)
    sent = taipei_iso(_text(root, "Sent"))
    cyclones = root.findall(".//{*}TropicalCyclone")
    if root.find(".//{*}TropicalCyclones") is None:
        raise ValueError("颱風檔案缺少 TropicalCyclones 欄位。")
    rows = []
    for cyclone in cyclones:
        analysis = cyclone.find("{*}AnalysisData")
        forecast = cyclone.find("{*}ForecastData")
        observed = sorted(
            (point for fix in (analysis.findall("{*}Fix") if analysis is not None else [])
             if (point := _position(fix)) is not None),
            key=lambda point: point["time"],
        )
        predicted = sorted(
            (point for fix in (forecast.findall("{*}Fix") if forecast is not None else [])
             if (point := _position(fix, True)) is not None),
            key=lambda point: point["time"],
        )
        if not observed:
            continue
        rows.append({
            "name": _text(cyclone, "CwaTyphoonName") or _text(cyclone, "TyphoonName") or "未命名熱帶氣旋",
            "english_name": _text(cyclone, "TyphoonName"),
            "observed": observed,
            "forecast": predicted,
            "latest_at": observed[-1]["time"],
        })
    return rows, sent
