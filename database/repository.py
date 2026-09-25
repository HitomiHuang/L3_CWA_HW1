from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

class ForecastRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.schema_path = Path(__file__).with_name("schema.sql")

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connection() as connection:
            connection.executescript(schema)

    def save_typhoon_run(self, dataset_id: str, fetched_at: str, source_updated: str | None,
                         cyclones: list[dict[str, Any]]) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO typhoon_runs (dataset_id, fetched_at, source_updated, cyclone_count, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (dataset_id, fetched_at, source_updated, len(cyclones),
                 json.dumps(cyclones, ensure_ascii=False, allow_nan=False)),
            )
        return int(cursor.lastrowid)

    def save_forecast_run(self, dataset_id: str, fetched_at: str, issue_time: str | None,
                          source_updated: str | None, rows: list[dict[str, Any]]) -> int:
        if not rows:
            raise ValueError("拒絕儲存空的預報批次。")
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO forecast_runs (dataset_id, fetched_at, issue_time, source_updated, record_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (dataset_id, fetched_at, issue_time, source_updated, len(rows)),
            )
            run_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO forecast_periods
                   (run_id, location, start_time, end_time, wx, weather_code, min_temp, max_temp, pop, comfort)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (run_id, location, start_time, end_time) DO UPDATE SET
                       wx = excluded.wx, weather_code = excluded.weather_code,
                       min_temp = excluded.min_temp, max_temp = excluded.max_temp,
                       pop = excluded.pop, comfort = excluded.comfort""",
                [(run_id, row["location"], row["start_time"], row["end_time"], row.get("wx"),
                  row.get("weather_code"), row.get("min_temp"), row.get("max_temp"), row.get("pop"), row.get("comfort"))
                 for row in rows],
            )
        return run_id

    def get_latest_run(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM forecast_runs ORDER BY fetched_at DESC, id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def record_crawl_result(self, dataset_id: str, started_at: str, finished_at: str,
                            status: str, record_count: int = 0, error_message: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO crawl_runs (dataset_id, started_at, finished_at, status, record_count, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dataset_id, started_at, finished_at, status, record_count, error_message),
            )

    def get_recent_crawl_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_runs(self, limit: int = 10):
        import pandas as pd
        with self._connection() as connection:
            return pd.read_sql_query(
                """SELECT id AS run_id, dataset_id, fetched_at, issue_time, source_updated, record_count
                   FROM forecast_runs ORDER BY fetched_at DESC, id DESC LIMIT ?""",
                connection,
                params=(limit,),
            )

    def save_weekly_run(self, dataset_id: str, fetched_at: str, source_updated: str | None,
                        rows: list[dict[str, Any]]) -> int:
        if not rows:
            raise ValueError("拒絕儲存空的一週預報批次。")
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO weekly_forecast_runs (dataset_id, fetched_at, source_updated, record_count) VALUES (?, ?, ?, ?)",
                (dataset_id, fetched_at, source_updated, len(rows)),
            )
            run_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO weekly_forecast_periods
                   (run_id, location, start_time, end_time, wx, description, min_temp, max_temp, pop, relative_humidity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (run_id, location, start_time, end_time) DO UPDATE SET
                       wx = excluded.wx, description = excluded.description,
                       min_temp = excluded.min_temp, max_temp = excluded.max_temp,
                       pop = excluded.pop, relative_humidity = excluded.relative_humidity""",
                [(run_id, row["location"], row["start_time"], row["end_time"], row.get("wx"), row.get("description"),
                  row.get("min_temp"), row.get("max_temp"), row.get("pop"), row.get("relative_humidity")) for row in rows],
            )
        return run_id

    def get_latest_weekly_run(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM weekly_forecast_runs ORDER BY fetched_at DESC, id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_weekly_periods(self, run_id: int, location: str | None = None):
        import pandas as pd
        query = """SELECT p.location, p.start_time, p.end_time, p.wx, p.description,
                          p.min_temp, p.max_temp, p.pop, p.relative_humidity, r.fetched_at
                   FROM weekly_forecast_periods AS p JOIN weekly_forecast_runs AS r ON r.id = p.run_id
                   WHERE p.run_id = ?"""
        parameters: list[Any] = [run_id]
        if location is not None:
            query += " AND p.location = ?"
            parameters.append(location)
        query += " ORDER BY p.location, p.start_time, p.end_time"
        with self._connection() as connection:
            return pd.read_sql_query(query, connection, params=parameters)

    def save_observation_run(self, dataset_id: str, fetched_at: str, source_updated: str | None,
                             rows: list[dict[str, Any]]) -> int:
        if not rows:
            raise ValueError("拒絕儲存空的測站觀測批次。")
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO observation_runs (dataset_id, fetched_at, source_updated, station_count) VALUES (?, ?, ?, ?)",
                (dataset_id, fetched_at, source_updated, len(rows)),
            )
            run_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO station_observations
                   (run_id, station_id, station_name, county, town, observed_at, latitude, longitude,
                    weather, temperature, relative_humidity, wind_speed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (run_id, station_id, observed_at) DO UPDATE SET
                       station_name = excluded.station_name, county = excluded.county, town = excluded.town,
                       latitude = excluded.latitude, longitude = excluded.longitude, weather = excluded.weather,
                       temperature = excluded.temperature, relative_humidity = excluded.relative_humidity,
                       wind_speed = excluded.wind_speed""",
                [(run_id, row["station_id"], row["station_name"], row.get("county"), row.get("town"), row["observed_at"],
                  row.get("latitude"), row.get("longitude"), row.get("weather"), row.get("temperature"),
                  row.get("relative_humidity"), row.get("wind_speed")) for row in rows],
            )
        return run_id

    def get_latest_observation_run(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM observation_runs ORDER BY fetched_at DESC, id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_observations(self, run_id: int, county: str | None = None):
        import pandas as pd
        query = """SELECT station_id, station_name, county, town, observed_at, latitude, longitude,
                          weather, temperature, relative_humidity, wind_speed
                   FROM station_observations WHERE run_id = ?"""
        parameters: list[Any] = [run_id]
        if county is not None:
            query += " AND county = ?"
            parameters.append(county)
        query += " ORDER BY observed_at DESC, station_name"
        with self._connection() as connection:
            return pd.read_sql_query(query, connection, params=parameters)

    def get_snapshot_history(self, location: str, start_time: str, end_time: str):
        import pandas as pd
        with self._connection() as connection:
            return pd.read_sql_query(
                """SELECT r.id AS run_id, r.fetched_at, p.wx, p.min_temp, p.max_temp, p.pop
                   FROM forecast_periods AS p JOIN forecast_runs AS r ON r.id = p.run_id
                   WHERE p.location = ? AND p.start_time = ? AND p.end_time = ?
                   ORDER BY r.fetched_at, r.id""",
                connection,
                params=(location, start_time, end_time),
            )

    def get_run_periods(self, run_id: int, location: str | None = None):
        import pandas as pd
        query = """SELECT p.location, p.start_time, p.end_time, p.wx, p.weather_code,
                          p.min_temp, p.max_temp, p.pop, p.comfort, r.fetched_at
                   FROM forecast_periods AS p JOIN forecast_runs AS r ON r.id = p.run_id
                   WHERE p.run_id = ?"""
        parameters: list[Any] = [run_id]
        if location is not None:
            query += " AND p.location = ?"
            parameters.append(location)
        query += " ORDER BY p.location, p.start_time, p.end_time"
        with self._connection() as connection:
            return pd.read_sql_query(query, connection, params=parameters)
