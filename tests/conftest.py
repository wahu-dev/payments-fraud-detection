"""Shared fixtures: a tiny warehouse where every answer is known by hand.

  txn step type      amount  sender  recipient  why it is here
   1    1  TRANSFER    100    A1      D1        fraud that empties the account; D1 is new
   2    1  CASH_OUT     50    A2      D1        same hour as txn 1: must NOT count it as history
   3    2  TRANSFER    200    A3      D1        D1 seen twice before; sender balance 0
   4   26  CASH_OUT     10    A4      D1        24h window covers steps 2-25 only (txn 3)
   5   27  PAYMENT       5    A5      M1        out of scope (payment to a merchant)
   6   30  TRANSFER    300    A1      D2        sender A1 seen once before
   7    3  CASH_OUT     20    A6      D3        legit, train
   8   20  TRANSFER     30    A7      D4        legit, valid
   9   40  CASH_OUT     40    A8      D5        legit, test
Split: train <= step 10, valid <= step 26, test after.
"""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.config import PROJECT_ROOT, load_config
from src.db import connect
from src.features import build_features
from src.load import load_transactions, write_split_config

SQL_DIR = PROJECT_ROOT / "sql" / "features"
COLUMNS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
           "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud"]
ROWS = [
    (1, "TRANSFER", 100.0, "A1", 100.0, 0.0, "D1", 0.0, 0.0, 1, 0),
    (1, "CASH_OUT", 50.0, "A2", 500.0, 450.0, "D1", 0.0, 50.0, 0, 0),
    (2, "TRANSFER", 200.0, "A3", 0.0, 0.0, "D1", 50.0, 250.0, 0, 0),
    (26, "CASH_OUT", 10.0, "A4", 1000.0, 990.0, "D1", 250.0, 260.0, 1, 0),
    (27, "PAYMENT", 5.0, "A5", 100.0, 95.0, "M1", 0.0, 0.0, 0, 0),
    (30, "TRANSFER", 300.0, "A1", 300.0, 0.0, "D2", 0.0, 0.0, 1, 0),
    (3, "CASH_OUT", 20.0, "A6", 900.0, 880.0, "D3", 10.0, 30.0, 0, 0),
    (20, "TRANSFER", 30.0, "A7", 700.0, 670.0, "D4", 5.0, 35.0, 0, 0),
    (40, "CASH_OUT", 40.0, "A8", 600.0, 560.0, "D5", 0.0, 40.0, 0, 0),
]


def rows_frame(rows=ROWS) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=COLUMNS)


@pytest.fixture
def cfg() -> dict:
    c = copy.deepcopy(load_config())
    c["split"] = {"train_end_step": 10, "valid_end_step": 26}
    return c


def build_warehouse(tmp_path, cfg, frame: pd.DataFrame, name: str = "tiny"):
    csv = tmp_path / f"{name}.csv"
    frame.to_csv(csv, index=False)
    con = connect(None)
    load_transactions(con, csv)
    write_split_config(con, cfg["split"]["train_end_step"], cfg["split"]["valid_end_step"])
    build_features(con, SQL_DIR)
    return con


@pytest.fixture
def con(tmp_path, cfg):
    connection = build_warehouse(tmp_path, cfg, rows_frame())
    yield connection
    connection.close()


@pytest.fixture
def model_rows(con) -> pd.DataFrame:
    """model_table indexed by txn_id (txn_id = row order in the CSV, from 1)."""
    from src.db import query_df
    return query_df(con, "SELECT * FROM model_table").set_index("txn_id").sort_index()
