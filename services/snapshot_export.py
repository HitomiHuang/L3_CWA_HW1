"""Publish a public, key-free JSON snapshot from the latest SQLite batches."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import CITY_COORDINATES, TIMEZONE


def build_snapshot(database_path: str | Path) -> dict:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        def latest(table: str) -> dict | None:
            row = connection.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

        def dataset(run_table: str, period_table: str, fields: str, count_key: str) -> dict:
            run = latest(run_table)
            if not run:
                return {"fetched_at": None, "source_updated": None, "count": 0, "rows": []}
            rows = connection.execute(
                f"SELECT {fields} FROM {period_table} WHERE run_id = ? ORDER BY id", (run["id"],)
            ).fetchall()
            return {
                "fetched_at": run["fetched_at"],
                "source_updated": run["source_updated"],
                "count": run[count_key],
                "rows": [dict(row) for row in rows],
            }

        crawls = [dict(row) for row in connection.execute(
            "SELECT dataset_id, started_at, finished_at, status, record_count, error_message "
            "FROM crawl_runs ORDER BY id DESC LIMIT 12"
        ).fetchall()]
        return {
            "schema_version": 1,
            "exported_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
            "timezone": TIMEZONE,
            "coordinates": CITY_COORDINATES,
            "forecast": dataset("forecast_runs", "forecast_periods",
                                "location, start_time, end_time, wx, weather_code, min_temp, max_temp, pop, comfort", "record_count"),
            "weekly": dataset("weekly_forecast_runs", "weekly_forecast_periods",
                              "location, start_time, end_time, wx, description, min_temp, max_temp, pop, relative_humidity", "record_count"),
            "observations": dataset("observation_runs", "station_observations",
                                    "station_id, station_name, county, town, observed_at, latitude, longitude, weather, "
                                    "temperature, relative_humidity, wind_speed", "station_count"),
            "crawl_runs": crawls,
        }
    finally:
        connection.close()


def export_snapshot(database_path: str | Path, output_path: str | Path) -> dict:
    data = build_snapshot(database_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return data
