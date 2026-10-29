"""Metrics for rare-event detection.

ROC-AUC flatters models when fraud is 0.1% of traffic, so the headline
metrics here are precision-recall based, plus the two numbers an operations
team cares about: how many alerts per day, and how much fraud VALUE is caught.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


def alert_summary(y: pd.Series, alerts: pd.Series, amount: pd.Series, days: pd.Series) -> dict:
    """Quality of a yes/no alert rule."""
    y = np.asarray(y).astype(int)
    alerts = np.asarray(alerts).astype(bool)
    amount = np.asarray(amount, dtype=float)
    tp = int((alerts & (y == 1)).sum())
    n_alerts = int(alerts.sum())
    fraud_value = float(amount[y == 1].sum())
    n_days = int(pd.Series(days).nunique())
    return {
        "alerts": n_alerts,
        "alerts_per_day": round(n_alerts / n_days, 1) if n_days else 0.0,
        "frauds": int(y.sum()),
        "frauds_caught": tp,
        "precision": round(tp / n_alerts, 4) if n_alerts else 0.0,
        "recall": round(tp / y.sum(), 4) if y.sum() else 0.0,
        "value_recall": round(float(amount[alerts & (y == 1)].sum()) / fraud_value, 4) if fraud_value else 0.0,
    }


def top_k_per_day(score: pd.Series, days: pd.Series, k: int) -> np.ndarray:
    """Boolean mask: the k highest scores within each day (ties broken by order)."""
    frame = pd.DataFrame({"score": np.asarray(score, dtype=float), "day": np.asarray(days)})
    rank = frame.groupby("day")["score"].rank(method="first", ascending=False)
    return (rank <= k).to_numpy()


def budget_summary(y, score, amount, days, k: int) -> dict:
    """Quality when the team can only review the top-k alerts each day."""
    mask = top_k_per_day(score, days, k)
    summary = alert_summary(y, mask, amount, days)
    summary["daily_budget"] = k
    return summary


def ranking_metrics(y, score) -> dict:
    y = np.asarray(y).astype(int)
    score = np.asarray(score, dtype=float)
    if y.min() == y.max():
        return {"roc_auc": None, "pr_auc": None}
    return {
        "roc_auc": round(float(roc_auc_score(y, score)), 4),
        "pr_auc": round(float(average_precision_score(y, score)), 4),
    }
