-- One row per in-scope transaction (TRANSFER and CASH_OUT, the only types
-- with fraud), with features known at the moment of the request, the label,
-- the legacy rule flag (baseline only) and the time-based split.
SELECT
    c.txn_id,
    c.step,
    c.day,
    c.hour_of_day,
    c.txn_type,
    CASE WHEN c.txn_type = 'TRANSFER' THEN 1 ELSE 0 END                 AS is_transfer,
    c.amount,
    LN(1 + c.amount)                                                     AS log_amount,
    c.orig_balance_before,
    c.dest_balance_before,
    CASE WHEN c.orig_balance_before = 0 THEN 1 ELSE 0 END               AS orig_zero_balance,
    CASE WHEN c.dest_balance_before = 0 THEN 1 ELSE 0 END               AS dest_zero_balance,
    c.amount / NULLIF(c.orig_balance_before, 0)                         AS amount_to_orig_balance,
    CASE WHEN c.orig_balance_before > 0
          AND c.amount >= c.orig_balance_before THEN 1 ELSE 0 END       AS drains_account,
    CASE WHEN c.dest_account LIKE 'M%' THEN 1 ELSE 0 END                AS dest_is_merchant,
    h.dest_prior_txns,
    h.dest_txns_prev_24h,
    h.dest_amount_prev_24h,
    h.dest_hours_since_first_seen,
    CASE WHEN h.dest_prior_txns = 0 THEN 1 ELSE 0 END                   AS dest_is_new,
    h.orig_prior_txns,
    c.legacy_flag,
    c.is_fraud,
    CASE WHEN c.step <= s.train_end_step THEN 'train'
         WHEN c.step <= s.valid_end_step THEN 'valid'
         ELSE 'test' END                                                AS split
FROM transactions_clean AS c
JOIN account_history AS h USING (txn_id)
CROSS JOIN split_config AS s
WHERE c.txn_type IN ('TRANSFER', 'CASH_OUT')
