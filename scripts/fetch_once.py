from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DATABASE_PATH
from database.repository import ForecastRepository
from services.weather_service import WeatherService


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch CWA weather datasets into the local SQLite database.")
    parser.add_argument("--all", action="store_true", help="also fetch one-week forecast and station observations")
    args = parser.parse_args()
    repository = ForecastRepository(DATABASE_PATH)
    repository.initialize()
    service = WeatherService(repository)
    jobs = [("36 小時預報", service.refresh)]
    if args.all:
        jobs.extend([
            ("一週預報", service.refresh_weekly_forecast),
            ("測站觀測", service.refresh_observations),
        ])
    failures = 0
    for label, refresh in jobs:
        try:
            run_id, count = refresh()
            print(f"{label}：已儲存批次 #{run_id}，共 {count} 筆資料。")
        except Exception as exc:
            print(f"{label} 更新失敗：{exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
