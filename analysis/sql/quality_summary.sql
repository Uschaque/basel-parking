-- Coverage and impossible values by garage.
SELECT
    garage_id,
    raw_rows,
    valid_rows,
    ROUND(invalid_pct, 2) AS invalid_pct,
    included,
    exclusion_reason
FROM quality_audit
ORDER BY included DESC, garage_id;

-- Median free spaces by garage, weekday and local hour.
SELECT
    garage_id,
    weekday,
    hour,
    COUNT(*) AS observations,
    AVG(free) AS mean_free_spaces
FROM observations
GROUP BY garage_id, weekday, hour
ORDER BY garage_id, weekday, hour;
