"""Rule-based baseline: what a payments team runs before it has a model.

Three readable rules plus the legacy flag already in the data. Every model in
later stages must beat this on the same days, the same alert budget and the
same metric, or it has not earned its complexity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics import alert_summary, ranking_metrics, top_k_per_day

RULES = {
    "r1_large_amount": "Amount at or above the large-amount limit",
    "r2_drains_account": "Empties the sender's account (and is not tiny)",
    "r3_large_to_new_recipient": "Large transfer to a recipient never seen before",
}
POINTS = {"r2_drains_account": 3, "r3_large_to_new_recipient": 2, "r1_large_amount": 1}


def rule_flags(df: pd.DataFrame, rules_cfg: dict) -> pd.DataFrame:
    flags = pd.DataFrame(index=df.index)
    flags["r1_large_amount"] = df["amount"] >= rules_cfg["large_amount"]
    flags["r2_drains_account"] = (df["drains_account"] == 1) & (df["amount"] >= rules_cfg["drain_min_amount"])
    flags["r3_large_to_new_recipient"] = (df["dest_is_new"] == 1) & (df["amount"] >= rules_cfg["new_dest_min_amount"])
    flags["any_rule"] = flags[list(RULES)].any(axis=1)
    return flags


def rule_score(df: pd.DataFrame, flags: pd.DataFrame) -> pd.Series:
    """Points per rule hit; amount breaks ties (larger first). Used to rank
    alerts when the team cannot review all of them."""
    points = sum(flags[r].astype(int) * p for r, p in POINTS.items())
    return points + df["amount"].astype(float) / 1e10


def evaluate_rules(df: pd.DataFrame, rules_cfg: dict, daily_budget: int) -> pd.DataFrame:
    """One row per rule (and the legacy flag, and the budgeted rule set)."""
    flags = rule_flags(df, rules_cfg)
    y, amount, days = df["is_fraud"], df["amount"], df["day"]
    rows = [{"rule": "legacy_flag", "description": "Existing system flag in the data",
             **alert_summary(y, df["legacy_flag"] == 1, amount, days)}]
    for name, text in RULES.items():
        rows.append({"rule": name, "description": text, **alert_summary(y, flags[name], amount, days)})
    rows.append({"rule": "any_rule", "description": "Any of R1-R3",
                 **alert_summary(y, flags["any_rule"], amount, days)})
    score = rule_score(df, flags)
    budget_mask = top_k_per_day(score, days, daily_budget) & flags["any_rule"].to_numpy()
    rows.append({"rule": f"any_rule_top_{daily_budget}_per_day",
                 "description": f"Any rule, only the top {daily_budget} alerts per day by points then amount",
                 **alert_summary(y, budget_mask, amount, days)})
    out = pd.DataFrame(rows)
    rank = ranking_metrics(y, score)
    out.attrs["ranking"] = rank
    return out
