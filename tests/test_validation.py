import pytest

from src.validate import ValidationError, validate


def test_tiny_warehouse_passes(con, cfg):
    assert all(c.passed for c in validate(con, cfg))


def test_duplicated_rows_fail(con, cfg):
    con.execute("INSERT INTO model_table SELECT * FROM model_table WHERE txn_id = 1")
    with pytest.raises(ValidationError, match="one row per transaction"):
        validate(con, cfg)


def test_leaked_column_fails(con, cfg):
    con.execute("ALTER TABLE model_table ADD COLUMN orig_balance_after DOUBLE")
    with pytest.raises(ValidationError, match="post-transaction"):
        validate(con, cfg)


def test_split_without_fraud_fails(con, cfg):
    con.execute("UPDATE model_table SET is_fraud = 0 WHERE split = 'test'")
    with pytest.raises(ValidationError, match="each have fraud"):
        validate(con, cfg)


def test_split_config_rejects_bad_boundaries(con):
    from src.load import write_split_config
    with pytest.raises(ValueError):
        write_split_config(con, 50, 40, 60)
