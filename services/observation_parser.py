from __future__ import annotations

from typing import Any

from services.parse_utils import clean_text, number, taipei_iso


def parse_station_observations(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Normalize O-A0001-001 station observations without treating forecasts as measurements."""
    records = payload.get("records") or {}
    stations = records.get("Station") or records.get("station") or []
    rows: list[dict[str, Any]] = []
    for station in stations:
        station_id = clean_text(station.get("StationId") or station.get("stationId"))
        station_name = clean_text(station.get("StationName") or station.get("stationName"))
        obs_time = station.get("ObsTime") or station.get("obsTime") or {}
        observed_at = taipei_iso(obs_time.get("DateTime") or obs_time.get("dateTime"))
        geo_info = station.get("GeoInfo") or station.get("geoInfo") or {}
        coordinates = geo_info.get("Coordinates") or geo_info.get("coordinates") or []
        coordinate = coordinates[0] if coordinates and isinstance(coordinates, list) else {}
        weather = station.get("WeatherElement") or station.get("weatherElement") or {}
        if not station_id or not observed_at:
            continue
        rows.append({
            "station_id": station_id,
            "station_name": station_name or station_id,
            "county": clean_text(geo_info.get("CountyName") or geo_info.get("countyName")),
            "town": clean_text(geo_info.get("TownName") or geo_info.get("townName")),
            "observed_at": observed_at,
            "latitude": number(coordinate.get("StationLatitude") or coordinate.get("stationLatitude")),
            "longitude": number(coordinate.get("StationLongitude") or coordinate.get("stationLongitude")),
            "weather": clean_text(weather.get("Weather") or weather.get("weather")),
            "temperature": number(weather.get("AirTemperature") or weather.get("airTemperature")),
            "relative_humidity": number(weather.get("RelativeHumidity") or weather.get("relativeHumidity")),
            "wind_speed": number(weather.get("WindSpeed") or weather.get("windSpeed")),
        })
    if not rows:
        raise ValueError("觀測 API 沒有可用的測站資料。")
    rows.sort(key=lambda row: (row["county"] or "", row["observed_at"], row["station_id"]))
    return rows, taipei_iso(payload.get("sent") or payload.get("Sent"))
