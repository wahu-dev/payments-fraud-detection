"""Load the PaySim CSV into the DuckDB warehouse with explicit column types.

Explicit types matter: letting the database guess from the first rows can
read a column as text or integer when it is not (that bit us in the credit
project). The file is already in time order; txn_id keeps that order.
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.db import table_row_count

log = logging.getLogger(__name__)

COLUMNS = {
    "step": "INTEGER",
    "type": "VARCHAR",
    "amount": "DOUBLE",
    "nameOrig": "VARCHAR",
    "oldbalanceOrg": "DOUBLE",
    "newbalanceOrig": "DOUBLE",
    "nameDest": "VARCHAR",
    "oldbalanceDest": "DOUBLE",
    "newbalanceDest": "DOUBLE",
    "isFraud": "INTEGER",
    "isFlaggedFraud": "INTEGER",
}


def _sql_path(path: Path) -> str:
    return Path(path).resolve().as_posix().replace("'", "''")


def load_transactions(con, csv_path: Path) -> int:
    """Create the raw `transactions` table. Returns the row count."""
    columns = ", ".join(f"'{name}': '{dtype}'" for name, dtype in COLUMNS.items())
    con.execute(
        "CREATE OR REPLACE TABLE transactions AS "
        "SELECT CAST(row_number() OVER () AS BIGINT) AS txn_id, * "
        f"FROM read_csv('{_sql_path(csv_path)}', header = true, columns = {{{columns}}})"
    )
    n = table_row_count(con, "transactions")
    log.info("Loaded %s transactions from %s", f"{n:,}", Path(csv_path).name)
    return n


def write_split_config(con, train_end_step: int, valid_end_step: int) -> None:
    """Store the split boundaries in the warehouse so the SQL can use them."""
    train_end_step, valid_end_step = int(train_end_step), int(valid_end_step)
    if not 0 < train_end_step < valid_end_step:
        raise ValueError("split: need 0 < train_end_step < valid_end_step")
    con.execute(
        "CREATE OR REPLACE TABLE split_config AS "
        f"SELECT {train_end_step} AS train_end_step, {valid_end_step} AS valid_end_step"
    )
