CREATE TABLE IF NOT EXISTS biometric_sample (
    time        TIMESTAMPTZ      NOT NULL,
    session_id  TEXT             NOT NULL,
    device_id   TEXT             NOT NULL,
    channel     TEXT             NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    unit        TEXT             NOT NULL,
    metadata    JSONB            NOT NULL DEFAULT '{}'::jsonb
);

SELECT create_hypertable(
    'biometric_sample',
    by_range('time'),
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS biometric_sample_session_time_idx
    ON biometric_sample (session_id, time DESC);

CREATE OR REPLACE VIEW biometric_5m AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    session_id,
    device_id,
    channel,
    count(*) AS samples,
    avg(value) AS mean,
    min(value) AS minimum,
    max(value) AS maximum
FROM biometric_sample
GROUP BY bucket, session_id, device_id, channel;
