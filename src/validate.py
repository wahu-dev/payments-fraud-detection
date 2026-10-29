"""Data validation gate: the pipeline stops if any check fails.

Cheap checks that catch expensive mistakes: duplicated rows from a bad join,
a leaked post-transaction column, an empty split, a label that is not 0/1.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.db import query_df, safe_identifier

log = logging.getLogger(__name__)


class ValidationError(RuntimeError):
    pass


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def run_checks(con, cfg: dict) -> list[Check]:
    table = safe_identifier(cfg["features"]["model_table"])
    in_scope = cfg["features"]["in_scope_types"]
    features = cfg["features"]["model_features"]
    forbidden = set(cfg["features"]["forbidden"])
    columns = set(query_df(con, f"DESCRIBE {table}")["column_name"])
    stats = query_df(con, f"""
        SELECT COUNT(*) AS n,
               COUNT(DISTINCT txn_id) AS n_ids,
               CAST(SUM(CASE WHEN is_fraud NOT IN (0, 1) OR is_fraud IS NULL THEN 1 ELSE 0 END) AS BIGINT) AS bad_labels,
               CAST(SUM(CASE WHEN amount < 0 OR amount IS NULL THEN 1 ELSE 0 END) AS BIGINT) AS bad_amounts
        FROM {table}""").iloc[0]
    types = set(query_df(con, f"SELECT DISTINCT txn_type FROM {table}")["txn_type"])
    splits = query_df(con, f"""
        SELECT split, COUNT(*) AS n, CAST(SUM(is_fraud) AS BIGINT) AS frauds FROM {table} GROUP BY split""")
    split_ok = {r.split: (r.n > 0 and r.frauds > 0 and r.frauds < r.n) for r in splits.itertuples()}

    leaked = sorted((forbidden - {"legacy_flag", "is_fraud"}) & columns)
    return [
        Check("table is not empty", int(stats.n) > 0, f"{int(stats.n):,} rows"),
        Check("one row per transaction", int(stats.n) == int(stats.n_ids),
              f"{int(stats.n) - int(stats.n_ids)} duplicated ids"),
        Check("labels are 0/1", int(stats.bad_labels) == 0, f"{int(stats.bad_labels)} bad labels"),
        Check("amounts are present and not negative", int(stats.bad_amounts) == 0,
              f"{int(stats.bad_amounts)} bad amounts"),
        Check("only in-scope transaction types", types <= set(in_scope), f"types found: {sorted(types)}"),
        Check("no post-transaction columns in the model table", not leaked, f"found: {leaked}"),
        Check("model features exist", set(features) <= columns, f"missing: {sorted(set(features) - columns)}"),
        Check("model features are not forbidden", not (set(features) & forbidden),
              f"forbidden in feature list: {sorted(set(features) & forbidden)}"),
        Check("train, valid and test each have fraud and non-fraud",
              {"train", "valid", "test"} <= set(split_ok)
              and all(split_ok[s] for s in ("train", "valid", "test")), f"{split_ok}"),
    ]


def validate(con, cfg: dict) -> list[Check]:
    checks = run_checks(con, cfg)
    for c in checks:
        log.info("%s %-50s %s", "PASS" if c.passed else "FAIL", c.name, c.detail)
    failed = [c for c in checks if not c.passed]
    if failed:
        raise ValidationError("Validation failed: " + "; ".join(f"{c.name} ({c.detail})" for c in failed))
    return checks
