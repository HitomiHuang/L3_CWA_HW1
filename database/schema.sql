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

CREATE TABLE IF NOT EXISTS weekly_forecast_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    source_updated TEXT,
    record_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_weekly_runs_fetched_at
    ON weekly_forecast_runs (fetched_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS weekly_forecast_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES weekly_forecast_runs(id) ON DELETE CASCADE,
    location TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    wx TEXT,
    description TEXT,
    min_temp REAL,
    max_temp REAL,
    pop REAL,
    relative_humidity REAL,
    UNIQUE (run_id, location, start_time, end_time)
);

CREATE INDEX IF NOT EXISTS idx_weekly_periods_run_location_time
    ON weekly_forecast_periods (run_id, location, start_time);

CREATE TABLE IF NOT EXISTS observation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    source_updated TEXT,
    station_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_observation_runs_fetched_at
    ON observation_runs (fetched_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS station_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES observation_runs(id) ON DELETE CASCADE,
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    county TEXT,
    town TEXT,
    observed_at TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    weather TEXT,
    temperature REAL,
    relative_humidity REAL,
    wind_speed REAL,
    UNIQUE (run_id, station_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_station_observations_run_county_time
    ON station_observations (run_id, county, observed_at DESC);
