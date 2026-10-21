-- Beginner SQL cookbook for the EmotiBit `biometric_sample` table.
-- Every query here is READ-ONLY. Paste one at a time into Tiger Cloud's SQL editor.
-- Replace 'test-simulation' with your own session_id.

-- 1. Which sessions exist, and how big are they?
SELECT session_id, device_id, channel,
       count(*)   AS samples,
       min(time)  AS started_at,
       max(time)  AS ended_at
FROM biometric_sample
GROUP BY session_id, device_id, channel
ORDER BY ended_at DESC;

-- 2. The 20 newest readings from one session.
SELECT time, value, unit
FROM biometric_sample
WHERE session_id = 'test-simulation' AND channel = 'eda'
ORDER BY time DESC
LIMIT 20;

-- 3. One average per 10 seconds. time_bucket() is TimescaleDB's "group by time window".
SELECT time_bucket('10 seconds', time) AS bucket,
       avg(value) AS mean,
       min(value) AS minimum,
       max(value) AS maximum
FROM biometric_sample
WHERE session_id = 'test-simulation' AND channel = 'eda'
GROUP BY bucket
ORDER BY bucket;

-- 4. Same thing, but fill gaps (seconds with no readings) with a NULL row so a
--    chart shows the hole instead of silently joining the dots.
SELECT time_bucket_gapfill('10 seconds', time) AS bucket,
       avg(value) AS mean
FROM biometric_sample
WHERE session_id = 'test-simulation' AND channel = 'eda'
  AND time BETWEEN now() - interval '1 day' AND now()
GROUP BY bucket
ORDER BY bucket;

-- 5. The built-in five-minute summary view created by sql/schema.sql.
SELECT bucket, mean, minimum, maximum, samples
FROM biometric_5m
WHERE session_id = 'test-simulation' AND channel = 'eda'
ORDER BY bucket;

-- 6. Compare two sessions side by side.
SELECT session_id,
       round(avg(value)::numeric, 3) AS mean_eda,
       round(stddev(value)::numeric, 3) AS spread,
       count(*) AS samples
FROM biometric_sample
WHERE session_id IN ('session-a', 'session-b') AND channel = 'eda'
GROUP BY session_id;

-- 7. Where did a session come from? Live bridge rows have empty metadata;
--    rows imported from an SD card carry {"source": "sd-card"}.
SELECT session_id, metadata, count(*)
FROM biometric_sample
GROUP BY session_id, metadata
ORDER BY session_id;

-- 8. How much disk is the hypertable using?
SELECT pg_size_pretty(hypertable_size('biometric_sample')) AS size;

-- 9. DANGER ZONE: delete one test session. Run the SELECT first, check the
--    count, and only then run the DELETE. A DELETE without WHERE removes everything.
-- SELECT count(*) FROM biometric_sample WHERE session_id = 'test-simulation';
-- DELETE FROM biometric_sample WHERE session_id = 'test-simulation';
