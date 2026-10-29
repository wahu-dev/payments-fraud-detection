-- Fields that are NOT allowed in any model, built here so the leakage audit
-- can show how strong (and how misleading) they are.
-- A balance "error" is the gap between the balance change and the amount.
-- In a real ledger it is zero by construction; in PaySim it is a simulator
-- artefact that separates fraud almost perfectly.
SELECT
    txn_id,
    orig_balance_after,
    dest_balance_after,
    orig_balance_before - amount - orig_balance_after   AS orig_balance_error,
    dest_balance_before + amount - dest_balance_after   AS dest_balance_error
FROM transactions_clean
