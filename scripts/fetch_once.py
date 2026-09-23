from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DATABASE_PATH
from database.repository import ForecastRepository
from services.weather_service import WeatherService


def main() -> int:
    repository = ForecastRepository(DATABASE_PATH)
    repository.initialize()
    try:
        run_id, count = WeatherService(repository).refresh()
    except Exception as exc:
        print(f"更新失敗：{exc}", file=sys.stderr)
        return 1
    print(f"已儲存預報批次 #{run_id}，共 {count} 筆資料。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
