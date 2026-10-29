-- Behaviour of the accounts involved, using ONLY earlier hours.
--
-- Why "1 PRECEDING": transactions inside the same hour have no reliable order
-- in the data, so counting them could let a transaction see activity that
-- happened after it. Only strictly earlier steps are used. This is the main
-- leakage guard for behaviour features (see tests/test_leakage.py).
--
-- The recipient side carries most of the signal: in PaySim almost every
-- sender appears once, but recipients (including mule accounts) repeat.
SELECT
    txn_id,
    COUNT(*)            OVER dest_past      AS dest_prior_txns,
    COUNT(*)            OVER dest_24h       AS dest_txns_prev_24h,
    COALESCE(SUM(amount) OVER dest_24h, 0)  AS dest_amount_prev_24h,
    step - MIN(step)    OVER dest_past      AS dest_hours_since_first_seen,  -- NULL if never seen
    COUNT(*)            OVER orig_past      AS orig_prior_txns
FROM transactions_clean
WINDOW
    dest_past AS (PARTITION BY dest_account ORDER BY step
                  RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
    dest_24h  AS (PARTITION BY dest_account ORDER BY step
                  RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING),
    orig_past AS (PARTITION BY orig_account ORDER BY step
                  RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
