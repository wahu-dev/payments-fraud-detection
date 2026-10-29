"""Leakage guards. These are the tests that keep stage 2 scores honest."""
from src.db import query_df
from src.leakage_audit import run_audit
from tests.conftest import ROWS, build_warehouse, rows_frame

POST_TRANSACTION = {"orig_balance_after", "dest_balance_after", "orig_balance_error", "dest_balance_error"}


def test_model_table_has_no_post_transaction_columns(con):
    columns = set(query_df(con, "DESCRIBE model_table")["column_name"])
    assert not (columns & POST_TRANSACTION)


def test_feature_list_is_clean(cfg, con):
    features = set(cfg["features"]["model_features"])
    columns = set(query_df(con, "DESCRIBE model_table")["column_name"])
    assert features <= columns
    assert not (features & set(cfg["features"]["forbidden"]))
    assert {"is_fraud", "legacy_flag", "split", "txn_id"}.isdisjoint(features)


def _features(con, cfg):
    cols = ", ".join(cfg["features"]["model_features"])
    return query_df(con, f"SELECT txn_id, {cols} FROM model_table ORDER BY txn_id").set_index("txn_id")


def test_future_transactions_do_not_change_past_features(tmp_path, cfg, con):
    later = (500, "TRANSFER", 9999.0, "A1", 9999.0, 0.0, "D1", 0.0, 0.0, 1, 0)
    with_future = build_warehouse(tmp_path, cfg, rows_frame(ROWS + [later]), name="future")
    before = _features(con, cfg)
    after = _features(with_future, cfg).loc[before.index]
    assert before.equals(after)


def test_same_hour_transactions_do_not_change_features(tmp_path, cfg, con):
    same_hour = (26, "TRANSFER", 777.0, "A9", 777.0, 0.0, "D1", 0.0, 0.0, 0, 0)
    extra = build_warehouse(tmp_path, cfg, rows_frame(ROWS + [same_hour]), name="samehour")
    before = _features(con, cfg)
    after = _features(extra, cfg).loc[before.index]
    assert before.equals(after)


def test_audit_marks_post_transaction_fields_forbidden(con, cfg):
    audit = run_audit(con, cfg).set_index("column")
    for col in POST_TRANSACTION | {"legacy_flag"}:
        assert audit.loc[col, "status"] == "forbidden"
    assert set(audit.index) >= set(cfg["features"]["model_features"])
