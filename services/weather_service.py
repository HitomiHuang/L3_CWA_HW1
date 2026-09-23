from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config import CWA_DATASET_ID, OBSERVATION_DATASET_ID, TIMEZONE, WEEKLY_DATASET_ID
from database.repository import ForecastRepository
from services.cwa_client import CWAClient
from services.forecast_parser import parse_36_hour_forecast, validate_forecast_rows
from services.observation_parser import parse_station_observations
from services.weekly_forecast_parser import parse_weekly_forecast


class WeatherService:
    def __init__(self, repository: ForecastRepository, client: CWAClient | None = None) -> None:
        self.repository = repository
        self.client = client or CWAClient()

    def _recorded(self, dataset_id: str, work) -> tuple[int, int]:
        started_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        try:
            run_id, count = work()
        except Exception as exc:
            finished_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
            message = str(exc)
            key = getattr(self.client, "api_key", "")
            if key:
                message = message.replace(key, "[redacted]")
            self.repository.record_crawl_result(dataset_id, started_at, finished_at, "failed", error_message=message[:500])
            raise
        finished_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        self.repository.record_crawl_result(dataset_id, started_at, finished_at, "success", count)
        return run_id, count

    def refresh(self) -> tuple[int, int]:
        return self._recorded(CWA_DATASET_ID, self._refresh_forecast)

    def _refresh_forecast(self) -> tuple[int, int]:
        payload = self.client.fetch_36_hour_forecast()
        rows, issue_time, source_updated = parse_36_hour_forecast(payload)
        validate_forecast_rows(rows)
        fetched_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        run_id = self.repository.save_forecast_run(CWA_DATASET_ID, fetched_at, issue_time, source_updated, rows)
        return run_id, len(rows)

    def refresh_weekly_forecast(self) -> tuple[int, int]:
        return self._recorded(WEEKLY_DATASET_ID, self._refresh_weekly)

    def _refresh_weekly(self) -> tuple[int, int]:
        payload = self.client.fetch_dataset(WEEKLY_DATASET_ID)
        rows, _, source_updated = parse_weekly_forecast(payload)
        validate_forecast_rows(rows)
        fetched_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        run_id = self.repository.save_weekly_run(WEEKLY_DATASET_ID, fetched_at, source_updated, rows)
        return run_id, len(rows)

    def refresh_observations(self) -> tuple[int, int]:
        return self._recorded(OBSERVATION_DATASET_ID, self._refresh_observations)

    def _refresh_observations(self) -> tuple[int, int]:
        payload = self.client.fetch_dataset(OBSERVATION_DATASET_ID)
        rows, source_updated = parse_station_observations(payload)
        fetched_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        run_id = self.repository.save_observation_run(OBSERVATION_DATASET_ID, fetched_at, source_updated, rows)
        return run_id, len(rows)
