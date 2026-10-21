-- Tiger Cloud schema for AWEAR EEG exports. Used by awear/upload_to_tiger.py.
-- Safe to run more than once: nothing here deletes data.
--
-- Each AWEAR record is one second of EEG: 256 samples at 256 Hz. We keep that
-- shape and store one row per record, with the 256 samples in an array column.
-- That is 3,600 rows per hour instead of 921,600, which keeps the table small
-- and uploads fast. See the unnest() query below for per-sample access.

CREATE TABLE IF NOT EXISTS eeg_record (
    time            TIMESTAMPTZ        NOT NULL,  -- start of the one-second record (UTC)
    participant_id  TEXT               NOT NULL,  -- opaque AWEAR id such as P-A1B2C3
    device_id       TEXT               NOT NULL,
    channel         TEXT               NOT NULL DEFAULT 'TP10',
    sampling_rate   INTEGER            NOT NULL DEFAULT 256,
    unit            TEXT               NOT NULL,  -- V, mV, or uV, as confirmed with AWEAR
    waveform        DOUBLE PRECISION[] NOT NULL,  -- 256 samples
    metadata        JSONB              NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (time, participant_id, device_id, channel)
);

SELECT create_hypertable(
    'eeg_record',
    by_range('time'),
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS eeg_record_participant_time_idx
    ON eeg_record (participant_id, time DESC);

-- How many seconds of EEG exist per participant, per hour.
CREATE OR REPLACE VIEW eeg_coverage_1h AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    participant_id,
    device_id,
    count(*)                    AS seconds_recorded,
    min(time)                   AS first_record,
    max(time)                   AS last_record
FROM eeg_record
GROUP BY bucket, participant_id, device_id;

-- Example (read-only): expand one minute of records into one row per sample.
-- SELECT r.time + ((u.i - 1) * interval '1 second' / r.sampling_rate) AS sample_time,
--        u.v AS value
-- FROM eeg_record AS r
-- CROSS JOIN LATERAL unnest(r.waveform) WITH ORDINALITY AS u(v, i)
-- WHERE r.participant_id = 'P-A1B2C3'
--   AND r.time >= '2026-10-15T09:00:00Z' AND r.time < '2026-10-15T09:01:00Z'
-- ORDER BY sample_time;
