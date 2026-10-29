"""Generate a small synthetic file in PaySim's exact format, for tests and CI.

The patterns are planted on purpose so the pipeline has something to find:
fraud only in TRANSFER and CASH_OUT, fraud usually empties the sender's
account, and stolen money goes to a small pool of mule accounts that receive
repeatedly. Numbers from this sample mean nothing; only the real data counts.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TYPES = ["CASH_OUT", "PAYMENT", "CASH_IN", "TRANSFER", "DEBIT"]
TYPE_SHARE = [0.35, 0.34, 0.22, 0.08, 0.01]
COLUMNS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
           "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud"]


def make_sample(n_rows: int = 40_000, seed: int = 42, fraud_rate: float = 0.02) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Busier first 400 hours, quieter later (as in the real data)
    weights = np.where(np.arange(1, 744) <= 400, 3.0, 1.0)
    step = np.sort(rng.choice(np.arange(1, 744), size=n_rows, p=weights / weights.sum()))
    txn_type = rng.choice(TYPES, size=n_rows, p=TYPE_SHARE)
    amount = np.round(np.exp(rng.normal(11, 1.2, n_rows)), 2)
    old_orig = np.round(np.exp(rng.normal(10.5, 1.8, n_rows)) * (rng.random(n_rows) > 0.3), 2)

    customers = np.array([f"C{rng.integers(10**8, 10**9)}" for _ in range(4_000)])
    mules = np.array([f"C{rng.integers(10**8, 10**9)}" for _ in range(150)])
    name_orig = np.array([f"C{x}" for x in rng.integers(10**8, 10**9, n_rows)])
    name_dest = rng.choice(customers, n_rows)
    is_payment = txn_type == "PAYMENT"
    name_dest[is_payment] = [f"M{x}" for x in rng.integers(10**8, 10**9, is_payment.sum())]
    old_dest = np.round(np.exp(rng.normal(11, 2, n_rows)) * (rng.random(n_rows) > 0.25), 2)
    old_dest[is_payment] = 0.0

    in_scope = np.isin(txn_type, ["TRANSFER", "CASH_OUT"])
    is_fraud = in_scope & (rng.random(n_rows) < fraud_rate / 0.43)
    # Fraud: drain the account (amount = balance) and send to a mule
    funded = is_fraud & (old_orig == 0)
    old_orig[funded] = np.round(np.exp(rng.normal(12, 1.2, funded.sum())), 2)
    drain = is_fraud & (rng.random(n_rows) < 0.9)
    amount[drain] = old_orig[drain]
    name_dest[is_fraud] = rng.choice(mules, is_fraud.sum())

    adds = txn_type == "CASH_IN"
    new_orig = np.where(adds, old_orig + amount, np.maximum(old_orig - amount, 0.0))
    new_dest = np.where(is_payment | adds, old_dest, old_dest + amount)
    # The PaySim artefact: fraud recipients often show zero balances before and after
    artefact = is_fraud & (rng.random(n_rows) < 0.5)
    old_dest[artefact] = 0.0
    new_dest[artefact] = 0.0
    flagged = is_fraud & (txn_type == "TRANSFER") & (amount > 1_000_000)

    return pd.DataFrame({
        "step": step, "type": txn_type, "amount": amount, "nameOrig": name_orig,
        "oldbalanceOrg": old_orig, "newbalanceOrig": np.round(new_orig, 2), "nameDest": name_dest,
        "oldbalanceDest": old_dest, "newbalanceDest": np.round(new_dest, 2),
        "isFraud": is_fraud.astype(int), "isFlaggedFraud": flagged.astype(int),
    })[COLUMNS]


def write_sample(path: Path, n_rows: int = 40_000, seed: int = 42) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_sample(n_rows, seed).to_csv(path, index=False)
    return path
