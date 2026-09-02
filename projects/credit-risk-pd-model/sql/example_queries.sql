-- Monthly default rate trend
SELECT
    observation_date,
    COUNT(*) AS accounts,
    SUM(default_flag) AS defaults,
    AVG(default_flag::NUMERIC) AS default_rate
FROM credit_risk.monthly_performance
GROUP BY observation_date
ORDER BY observation_date;

-- Portfolio exposure by loan purpose
SELECT
    l.purpose,
    COUNT(*) AS loans,
    SUM(mp.outstanding_balance) AS exposure,
    AVG(mp.default_flag::NUMERIC) AS default_rate
FROM credit_risk.loans l
JOIN credit_risk.monthly_performance mp
    ON l.loan_id = mp.loan_id
GROUP BY l.purpose
ORDER BY exposure DESC;

-- Delinquency roll-rate style summary
SELECT
    observation_date,
    CASE
        WHEN days_past_due = 0 THEN 'current'
        WHEN days_past_due BETWEEN 1 AND 29 THEN 'dpd_1_29'
        WHEN days_past_due BETWEEN 30 AND 59 THEN 'dpd_30_59'
        WHEN days_past_due BETWEEN 60 AND 89 THEN 'dpd_60_89'
        ELSE 'dpd_90_plus'
    END AS delinquency_bucket,
    COUNT(*) AS accounts,
    SUM(outstanding_balance) AS balance
FROM credit_risk.monthly_performance
GROUP BY observation_date, delinquency_bucket
ORDER BY observation_date, delinquency_bucket;

