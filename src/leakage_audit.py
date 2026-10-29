"""Leakage audit: how much does each column alone separate fraud?

A single column that separates fraud almost perfectly is usually not a great
feature. It is usually leakage: information that is only known after the
event, or an artefact of how the data was made. PaySim has both, which is why
many public notebooks report 0.99+ scores that would never hold in production.

The audit scores every candidate column on the TRAIN period only and labels it
allowed / forbidden (with the reason from config.yaml). Allowed columns that
look too good to be true are marked "check".
"""
from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src.db import query_df, safe_identifier

TOO_GOOD = 0.95


def audit_frame(con, cfg: dict) -> pd.DataFrame:
    table = safe_identifier(cfg["features"]["model_table"])
    forbidden = [c for c in cfg["features"]["forbidden"] if c != "is_fraud"]
    cols = sorted(set(cfg["features"]["model_features"]) | set(forbidden))
    select = ", ".join(f"m.{c}" if c not in ("orig_balance_after", "dest_balance_after",
                                                "orig_balance_error", "dest_balance_error")
                       else f"a.{c}" for c in cols)
    return query_df(con, f"""
        SELECT {select}, m.is_fraud
        FROM {table} AS m JOIN audit_fields AS a USING (txn_id)
        WHERE m.split = 'train'""")


def single_feature_strength(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    """Direction-free ROC-AUC and the PR-AUC in that direction."""
    x = pd.to_numeric(x, errors="coerce").astype(float)
    x = x.fillna(x.min() - 1 if x.notna().any() else 0)
    if x.nunique() < 2:
        return 0.5, float(y.mean())
    auc = roc_auc_score(y, x)
    sign = 1.0 if auc >= 0.5 else -1.0
    return max(auc, 1 - auc), average_precision_score(y, sign * x)


def run_audit(con, cfg: dict) -> pd.DataFrame:
    frame = audit_frame(con, cfg)
    y = frame.pop("is_fraud").astype(int)
    reasons = cfg["features"]["forbidden"]
    rows = []
    for col in frame.columns:
        roc, pr = single_feature_strength(frame[col], y)
        is_forbidden = col in reasons
        status = "forbidden" if is_forbidden else ("check" if roc >= TOO_GOOD else "allowed")
        rows.append({"column": col, "status": status, "roc_auc": round(roc, 4), "pr_auc": round(pr, 4),
                     "reason": reasons.get(col, "known when the transaction is requested")})
    order = {"forbidden": 0, "check": 1, "allowed": 2}
    out = pd.DataFrame(rows)
    out["_order"] = out["status"].map(order)
    out = out.sort_values(["_order", "roc_auc"], ascending=[True, False])
    return out.drop(columns="_order").reset_index(drop=True)
