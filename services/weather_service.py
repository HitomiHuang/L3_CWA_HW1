from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config import CWA_DATASET_ID, TIMEZONE
from database.repository import ForecastRepository
from services.cwa_client import CWAClient
from services.forecast_parser import parse_36_hour_forecast, validate_forecast_rows


class WeatherService:
    def __init__(self, repository: ForecastRepository, client: CWAClient | None = None) -> None:
        self.repository = repository
        self.client = client or CWAClient()

    def refresh(self) -> tuple[int, int]:
        payload = self.client.fetch_36_hour_forecast()
        rows, issue_time, source_updated = parse_36_hour_forecast(payload)
        validate_forecast_rows(rows)
        fetched_at = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
        run_id = self.repository.save_forecast_run(CWA_DATASET_ID, fetched_at, issue_time, source_updated, rows)
        return run_id, len(rows)
