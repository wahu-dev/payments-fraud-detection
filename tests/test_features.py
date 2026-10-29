"""SQL features: every expected value below was worked out by hand (see conftest)."""
import pandas as pd


def test_only_transfers_and_cash_outs_are_in_scope(model_rows):
    assert 5 not in model_rows.index            # the merchant payment
    assert len(model_rows) == 10


def test_simulation_clock(model_rows):
    assert (model_rows.loc[1, "day"], model_rows.loc[1, "hour_of_day"]) == (1, 0)
    assert (model_rows.loc[4, "day"], model_rows.loc[4, "hour_of_day"]) == (2, 1)   # step 26


def test_same_hour_activity_is_not_history(model_rows):
    # txn 2 happens in the same hour as txn 1 to the same recipient
    assert model_rows.loc[2, "dest_prior_txns"] == 0
    assert model_rows.loc[2, "dest_is_new"] == 1


def test_recipient_history_counts_earlier_hours(model_rows):
    row = model_rows.loc[3]
    assert row["dest_prior_txns"] == 2
    assert row["dest_txns_prev_24h"] == 2
    assert row["dest_amount_prev_24h"] == 150.0
    assert row["dest_hours_since_first_seen"] == 1
    assert row["dest_is_new"] == 0


def test_24_hour_window_boundary(model_rows):
    # step 26 looks back to steps 2-25: txn 3 (step 2) is in, txns 1-2 (step 1) are out
    row = model_rows.loc[4]
    assert row["dest_prior_txns"] == 3
    assert row["dest_txns_prev_24h"] == 1
    assert row["dest_amount_prev_24h"] == 200.0
    assert row["dest_hours_since_first_seen"] == 25


def test_new_recipient_has_no_age(model_rows):
    assert pd.isna(model_rows.loc[1, "dest_hours_since_first_seen"])
    assert model_rows.loc[1, "dest_amount_prev_24h"] == 0


def test_sender_history(model_rows):
    assert model_rows.loc[1, "orig_prior_txns"] == 0
    assert model_rows.loc[6, "orig_prior_txns"] == 1      # A1 sent at step 1


def test_account_drain_flag(model_rows):
    assert model_rows.loc[1, "drains_account"] == 1      # sends the whole balance
    assert model_rows.loc[2, "drains_account"] == 0
    assert model_rows.loc[3, "drains_account"] == 0      # zero balance is not a drain


def test_ratio_is_missing_when_balance_is_zero(model_rows):
    assert pd.isna(model_rows.loc[3, "amount_to_orig_balance"])
    assert model_rows.loc[2, "amount_to_orig_balance"] == 0.1
    assert model_rows.loc[3, "orig_zero_balance"] == 1


def test_time_split_boundaries(model_rows):
    assert model_rows.loc[3, "split"] == "train"
    assert model_rows.loc[4, "split"] == "valid"          # step 26 = last valid hour
    assert model_rows.loc[6, "split"] == "test"
    assert model_rows.loc[11, "split"] == "test"          # step 33
    assert model_rows.loc[9, "split"] == "shifted"        # after the test period
