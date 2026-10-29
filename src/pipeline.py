"""Stage 1: load, build features, validate, audit leakage, score the rules baseline.

    python -m src.pipeline            # real PaySim data (downloads it if missing)
    python -m src.pipeline --sample   # synthetic sample, a few seconds (tests/CI)
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from src.config import load_config, project_path
from src.db import connect, query_df, safe_identifier
from src.download import download_dataset
from src.features import build_features
from src.leakage_audit import run_audit
from src.load import load_transactions, write_split_config
from src.make_sample_data import write_sample
from src.metrics import ranking_metrics
from src.rules import evaluate_rules
from src.validate import validate

log = logging.getLogger("pipeline")

RULE_COLUMNS = ["txn_id", "day", "amount", "drains_account", "dest_is_new", "legacy_flag", "is_fraud", "split"]


def data_profile(con, table: str) -> dict:
    overall = query_df(con, """
        SELECT COUNT(*) AS rows, CAST(SUM(isFraud) AS BIGINT) AS frauds, MAX(step) AS last_step FROM transactions""").iloc[0]
    by_type = query_df(con, """
        SELECT type, COUNT(*) AS rows, CAST(SUM(isFraud) AS BIGINT) AS frauds
        FROM transactions GROUP BY type ORDER BY rows DESC""")
    splits = query_df(con, f"""
        SELECT split, MIN(day) AS first_day, MAX(day) AS last_day, COUNT(*) AS rows,
               CAST(SUM(is_fraud) AS BIGINT) AS frauds, ROUND(100.0 * AVG(is_fraud), 3) AS fraud_pct
        FROM {table} GROUP BY split ORDER BY MIN(step)""")
    return {
        "transactions": int(overall.rows), "frauds": int(overall.frauds),
        "fraud_pct": round(100 * int(overall.frauds) / int(overall.rows), 3),
        "hours": int(overall.last_step),
        "by_type": by_type.astype({"rows": int, "frauds": int}).to_dict("records"),
        "splits": splits.astype({"rows": int, "frauds": int}).to_dict("records"),
    }


def run(sample: bool = False) -> dict:
    cfg = load_config()
    data = cfg["data"]
    if sample:
        sample_dir = project_path(data["sample_dir"])
        csv_path = write_sample(sample_dir / "paysim_sample.csv", data["sample_rows"], cfg["project"]["random_seed"])
        warehouse = sample_dir / "warehouse.duckdb"
        reports = project_path(cfg["reports_dir"]) / "sample"
    else:
        csv_path = download_dataset(data["kaggle_dataset"], project_path(data["raw_dir"]), data["raw_file"])
        warehouse = project_path(data["warehouse"])
        reports = project_path(cfg["reports_dir"])
    reports.mkdir(parents=True, exist_ok=True)
    table = safe_identifier(cfg["features"]["model_table"])

    con = connect(warehouse)
    try:
        load_transactions(con, csv_path)
        write_split_config(con, cfg["split"]["train_end_step"], cfg["split"]["valid_end_step"])
        build_features(con, project_path(cfg["features"]["sql_dir"]))
        validate(con, cfg)
        profile = data_profile(con, table)

        audit = run_audit(con, cfg)
        audit.to_csv(reports / "leakage_audit.csv", index=False)

        frame = query_df(con, f"SELECT {', '.join(RULE_COLUMNS)} FROM {table} WHERE split IN ('valid', 'test')")
    finally:
        con.close()

    budget = cfg["alerting"]["daily_alert_budget"]
    rule_tables = []
    rule_ranking = {}
    for split in ["valid", "test"]:
        part = frame[frame["split"] == split]
        result = evaluate_rules(part, cfg["rules"], budget)
        rule_ranking[split] = result.attrs["ranking"]
        rule_tables.append(result.assign(split=split))
    rules = pd.concat(rule_tables, ignore_index=True)
    rules.to_csv(reports / "rules_baseline.csv", index=False)

    summary = {"data": profile, "leakage_audit": audit.to_dict("records"),
               "rules_baseline": rules.to_dict("records"), "rules_ranking": rule_ranking}
    (reports / "stage1_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _print_summary(profile, audit, rules[rules["split"] == "test"], rule_ranking["test"], budget)
    log.info("Reports written to %s", reports)
    return summary


def _print_summary(profile: dict, audit: pd.DataFrame, rules: pd.DataFrame, ranking: dict, budget: int) -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print("\n=== Data ===")
    print(f"{profile['transactions']:,} transactions over {profile['hours']} hours, "
          f"{profile['frauds']:,} frauds ({profile['fraud_pct']}%)")
    print(pd.DataFrame(profile["by_type"]).to_string(index=False))
    print("\nIn-scope transactions (TRANSFER and CASH_OUT) by time split:")
    print(pd.DataFrame(profile["splits"]).to_string(index=False))
    print("\n=== Leakage audit (train period, one column at a time) ===")
    print(audit[["column", "status", "roc_auc", "pr_auc"]].to_string(index=False))
    print("\n=== Rules baseline on the TEST period ===")
    cols = ["rule", "alerts_per_day", "frauds_caught", "frauds", "precision", "recall", "value_recall"]
    print(rules[cols].to_string(index=False))
    print(f"\nRule score as a ranking: ROC-AUC {ranking['roc_auc']}, PR-AUC {ranking['pr_auc']} "
          f"(the number stage 2 models must beat). Daily alert budget: {budget}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1 pipeline")
    parser.add_argument("--sample", action="store_true", help="use the synthetic sample")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    run(sample=args.sample)


if __name__ == "__main__":
    main()
