"""Offline checks for the crawler, SQLite audit trail, and static export."""

import json
import tempfile
import unittest
from pathlib import Path

from database.repository import ForecastRepository
from services.snapshot_export import export_snapshot
from services.weather_service import WeatherService


FIXTURE = Path(__file__).parent / "fixtures" / "sample_forecast.json"


class FakeClient:
    api_key = "private-test-key"

    def fetch_36_hour_forecast(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def fetch_dataset(self, dataset_id):
        if dataset_id == "F-D0047-091":
            return {"records": {"Locations": [{"Location": [{
                "LocationName": "臺中市", "WeatherElement": [{
                    "ElementName": "最高溫度", "Time": [{
                        "StartTime": "2026-09-24T06:00:00+08:00",
                        "EndTime": "2026-09-24T18:00:00+08:00",
                        "ElementValue": [{"MaxTemperature": "32"}],
                    }],
                }],
            }]}]}}
        return {"records": {"Station": [{
            "StationId": "A001", "StationName": "測試站",
            "ObsTime": {"DateTime": "2026-09-24T11:00:00+08:00"},
            "GeoInfo": {"CountyName": "臺中市", "TownName": "西區",
                        "Coordinates": [{"StationLatitude": "24.15", "StationLongitude": "120.67"}]},
            "WeatherElement": {"AirTemperature": "29", "RelativeHumidity": "70"},
        }]}}


class FailingClient(FakeClient):
    def fetch_36_hour_forecast(self):
        raise RuntimeError("request failed: private-test-key")


class CrawlerSnapshotTest(unittest.TestCase):
    def test_success_and_failure_are_audited_and_export_has_no_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "weather.db"
            output = Path(directory) / "snapshot.json"
            repository = ForecastRepository(database)
            repository.initialize()
            service = WeatherService(repository, FakeClient())
            self.assertEqual(service.refresh()[1], 1)
            self.assertEqual(service.refresh_weekly_forecast()[1], 1)
            self.assertEqual(service.refresh_observations()[1], 1)
            with self.assertRaises(RuntimeError):
                WeatherService(repository, FailingClient()).refresh()

            snapshot = export_snapshot(database, output)
            self.assertEqual(snapshot["forecast"]["count"], 1)
            self.assertEqual(snapshot["weekly"]["count"], 1)
            self.assertEqual(snapshot["observations"]["count"], 1)
            self.assertEqual(snapshot["crawl_runs"][0]["status"], "failed")
            self.assertEqual(snapshot["crawl_runs"][1]["status"], "success")
            self.assertNotIn("private-test-key", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
