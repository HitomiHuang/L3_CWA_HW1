PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS forecast_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    issue_time TEXT,
    source_updated TEXT,
    record_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_fetched_at
    ON forecast_runs (fetched_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS forecast_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    location TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    wx TEXT,
    weather_code TEXT,
    min_temp REAL,
    max_temp REAL,
    pop REAL,
    comfort TEXT,
    UNIQUE (run_id, location, start_time, end_time)
);

CREATE INDEX IF NOT EXISTS idx_forecast_periods_run_location_time
    ON forecast_periods (run_id, location, start_time);
