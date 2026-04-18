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
