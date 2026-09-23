from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pandas as pd


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

    def get_recent_runs(self, limit: int = 10) -> pd.DataFrame:
        with self._connection() as connection:
            return pd.read_sql_query(
                """SELECT id AS run_id, dataset_id, fetched_at, issue_time, source_updated, record_count
                   FROM forecast_runs ORDER BY fetched_at DESC, id DESC LIMIT ?""",
                connection,
                params=(limit,),
            )

    def get_run_periods(self, run_id: int, location: str | None = None) -> pd.DataFrame:
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
