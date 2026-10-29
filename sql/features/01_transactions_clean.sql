-- Clean names and the simulation clock. One row per transaction.
-- step is the simulation hour (1 = first hour of day 1).
SELECT
    txn_id,
    step,
    (step - 1) // 24 + 1        AS day,
    (step - 1) % 24             AS hour_of_day,
    type                        AS txn_type,
    amount,
    nameOrig                    AS orig_account,
    nameDest                    AS dest_account,
    oldbalanceOrg               AS orig_balance_before,
    oldbalanceDest              AS dest_balance_before,
    -- Post-transaction balances: kept for the leakage audit only.
    newbalanceOrig              AS orig_balance_after,
    newbalanceDest              AS dest_balance_after,
    isFlaggedFraud              AS legacy_flag,
    isFraud                     AS is_fraud
FROM transactions
