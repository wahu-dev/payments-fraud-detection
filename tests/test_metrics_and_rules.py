"""Metrics and rules, checked against numbers worked out by hand."""
import numpy as np
import pandas as pd

from src.make_sample_data import make_sample
from src.metrics import alert_summary, top_k_per_day
from src.rules import evaluate_rules, rule_flags

RULES_CFG = {"large_amount": 1000, "drain_min_amount": 100, "new_dest_min_amount": 500}


def test_alert_summary():
    y = [1, 1, 0, 0, 1]
    alerts = [True, False, True, False, True]
    amount = [100, 300, 50, 50, 600]
    s = alert_summary(y, alerts, amount, days=[1, 1, 1, 2, 2])
    assert s["alerts"] == 3 and s["alerts_per_day"] == 1.5
    assert s["frauds_caught"] == 2 and s["frauds"] == 3
    assert s["precision"] == round(2 / 3, 4)
    assert s["recall"] == round(2 / 3, 4)
    assert s["value_recall"] == 0.7                       # (100 + 600) / 1000


def test_top_k_per_day_keeps_best_scores_each_day():
    mask = top_k_per_day(score=[0.9, 0.1, 0.5, 0.2, 0.8], days=[1, 1, 1, 2, 2], k=2)
    assert mask.tolist() == [True, False, True, True, True]


def _frame():
    return pd.DataFrame({
        "amount":         [2000, 150, 600, 50, 700],
        "drains_account": [0,    1,   0,   1,  0],
        "dest_is_new":    [0,    0,   1,   0,  0],
        "legacy_flag":    [1,    0,   0,   0,  0],
        "is_fraud":       [1,    1,   1,   0,  0],
        "day":            [1,    1,   1,   2,  2],
    })


def test_rule_flags():
    flags = rule_flags(_frame(), RULES_CFG)
    assert flags["r1_large_amount"].tolist() == [True, False, False, False, False]
    assert flags["r2_drains_account"].tolist() == [False, True, False, False, False]   # 50 is too small
    assert flags["r3_large_to_new_recipient"].tolist() == [False, False, True, False, False]
    assert flags["any_rule"].sum() == 3


def test_budget_keeps_highest_points_first():
    result = evaluate_rules(_frame(), RULES_CFG, daily_budget=1).set_index("rule")
    assert result.loc["any_rule", "frauds_caught"] == 3
    # Day 1 has three alerts; with a budget of 1 only the drain (3 points) survives
    budget = result.loc["any_rule_top_1_per_day"]
    assert budget["alerts"] == 1 and budget["frauds_caught"] == 1
    assert result.loc["legacy_flag", "frauds_caught"] == 1


def test_sample_data_matches_paysim_format():
    df = make_sample(2_000, seed=1)
    assert list(df.columns) == ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
                                "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud"]
    assert set(df.loc[df["isFraud"] == 1, "type"]) <= {"TRANSFER", "CASH_OUT"}
    assert df["step"].between(1, 743).all() and np.all(np.diff(df["step"]) >= 0)
