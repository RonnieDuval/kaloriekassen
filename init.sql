CREATE TABLE IF NOT EXISTS raw_mfp (
    date DATE PRIMARY KEY,
    calories_in INT,
    protein INT,
    carbs INT,
    fat INT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_intervals (
    date DATE PRIMARY KEY,
    calories_out INT,
    distance_km FLOAT,
    elevation_gain INT,
    workout_type TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_fitbit (
    date DATE PRIMARY KEY,
    calories_out INT,
    distance_km FLOAT,
    steps INT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_event (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_event_type TEXT NOT NULL,
    source_event_id TEXT,
    event_ts TIMESTAMPTZ,
    event_date DATE,
    payload_sha256 TEXT NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_event_type, payload_sha256)
);

CREATE INDEX IF NOT EXISTS idx_raw_event_source_date ON raw_event (source, event_date);

CREATE TABLE IF NOT EXISTS activity (
    id BIGSERIAL PRIMARY KEY,
    canonical_uid TEXT NOT NULL UNIQUE,
    start_ts TIMESTAMPTZ,
    end_ts TIMESTAMPTZ,
    activity_type TEXT,
    calories_out INT,
    distance_m INT,
    steps INT,
    dedupe_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_dedupe_key ON activity (dedupe_key);

CREATE TABLE IF NOT EXISTS activity_source_link (
    id BIGSERIAL PRIMARY KEY,
    activity_id BIGINT NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_activity_id TEXT NOT NULL,
    raw_event_id BIGINT REFERENCES raw_event(id) ON DELETE SET NULL,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_activity_id)
);

CREATE TABLE IF NOT EXISTS nutrition_entry (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_entry_id TEXT NOT NULL,
    consumed_ts TIMESTAMPTZ,
    entry_date DATE NOT NULL,
    meal_name TEXT,
    food_name TEXT,
    calories INT,
    protein_g NUMERIC(10,2),
    carbs_g NUMERIC(10,2),
    fat_g NUMERIC(10,2),
    raw_event_id BIGINT REFERENCES raw_event(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_entry_id)
);

CREATE TABLE IF NOT EXISTS export_google_health_activity (
    id BIGSERIAL PRIMARY KEY,
    activity_id BIGINT NOT NULL REFERENCES activity(id) ON DELETE CASCADE,
    export_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    external_id TEXT,
    attempts INT NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (activity_id, export_hash)
);

CREATE TABLE IF NOT EXISTS export_google_health_nutrition (
    id BIGSERIAL PRIMARY KEY,
    nutrition_entry_id BIGINT NOT NULL REFERENCES nutrition_entry(id) ON DELETE CASCADE,
    export_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    external_id TEXT,
    attempts INT NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (nutrition_entry_id, export_hash)
);

CREATE OR REPLACE VIEW daily_balance AS
SELECT
    d.date,
    m.calories_in,
    COALESCE(i.calories_out, f.calories_out, 0) AS calories_out,
    CASE
        WHEN i.date IS NOT NULL THEN 'intervals.icu'
        WHEN f.date IS NOT NULL THEN 'fitbit'
        ELSE NULL
    END AS calories_out_source,
    COALESCE(m.calories_in, 0) - COALESCE(i.calories_out, f.calories_out, 0) AS net_balance
FROM (
    SELECT date FROM raw_mfp
    UNION
    SELECT date FROM raw_intervals
    UNION
    SELECT date FROM raw_fitbit
) d
LEFT JOIN raw_mfp m ON m.date = d.date
LEFT JOIN raw_intervals i ON i.date = d.date
LEFT JOIN raw_fitbit f ON f.date = d.date
ORDER BY d.date;
