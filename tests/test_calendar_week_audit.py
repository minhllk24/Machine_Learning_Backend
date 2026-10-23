"""
Automated tests for calendar week audit and partial-week reconciliation.
Verifies:
- Total calendar weeks (106) vs active transaction weeks (104) vs holiday shutdown weeks (2).
- First partial week (Nov 30, 2009) and last partial week (Dec 5, 2011) detection.
- Exact Monday-to-Sunday weekly interval [week_start, week_end_exclusive).
- Exact boundary timestamp assignment (Sunday, Monday, Tuesday, millisecond boundaries).
"""
from pathlib import Path
import pandas as pd
import pytest
from src.config import CALENDAR_WEEK_AUDIT, RAW_EXCEL, INTERIM_DIR


@pytest.fixture
def calendar_audit():
    assert CALENDAR_WEEK_AUDIT.exists(), f"Missing {CALENDAR_WEEK_AUDIT}"
    df = pd.read_csv(CALENDAR_WEEK_AUDIT)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_end_exclusive"] = pd.to_datetime(df["week_end_exclusive"])
    return df


def test_calendar_week_count_against_raw_min_max(calendar_audit):
    """Verify total calendar weeks against raw dataset span."""
    raw_df = pd.read_parquet(INTERIM_DIR / "raw_transactions.parquet")
    min_date = pd.to_datetime(raw_df["InvoiceDate"].min())
    max_date = pd.to_datetime(raw_df["InvoiceDate"].max())
    
    # Raw dataset span: 2009-12-01 (Tuesday) to 2011-12-09 (Friday)
    assert min_date.strftime("%Y-%m-%d") == "2009-12-01"
    assert max_date.strftime("%Y-%m-%d") == "2011-12-09"
    
    # Earliest Monday floor: 2009-11-30; Latest Monday floor: 2011-12-05
    expected_start = pd.Timestamp("2009-11-30")
    expected_end = pd.Timestamp("2011-12-05")
    
    assert calendar_audit["week_start"].min() == expected_start
    assert calendar_audit["week_start"].max() == expected_end
    
    # 735 days = 105 * 7 days span -> exactly 106 weekly labels
    assert len(calendar_audit) == 106
    
    # Exactly 2 weeks had zero store transactions due to Christmas/New Year shutdown
    zero_tx_weeks = calendar_audit[calendar_audit["transaction_count"] == 0]
    assert len(zero_tx_weeks) == 2
    assert set(zero_tx_weeks["week_start"].dt.strftime("%Y-%m-%d")) == {"2009-12-28", "2010-12-27"}
    
    # Weeks with active transactions = 106 - 2 = 104
    assert (calendar_audit["transaction_count"] > 0).sum() == 104


def test_first_and_last_partial_week_detection(calendar_audit):
    """Verify boundary partial weeks at start and end of series."""
    # Week 1
    w1 = calendar_audit.iloc[0]
    assert w1["week_start"] == pd.Timestamp("2009-11-30")
    assert w1["is_partial_observation_week"] == True
    assert w1["is_zero_transaction_week"] == False
    assert w1["store_closure_status"] == "operating"
    assert w1["scoring_eligibility"] == "EXCLUDED_BOUNDARY_PARTIAL"
    assert w1["observed_calendar_days"] == 6  # Dec 1 to Dec 6
    assert w1["period_role"] == "EXCLUDED_BOUNDARY_START"
    
    # Week 106
    w_last = calendar_audit.iloc[-1]
    assert w_last["week_start"] == pd.Timestamp("2011-12-05")
    assert w_last["is_partial_observation_week"] == True
    assert w_last["is_zero_transaction_week"] == False
    assert w_last["store_closure_status"] == "operating"
    assert w_last["scoring_eligibility"] == "EXCLUDED_BOUNDARY_PARTIAL"
    assert w_last["observed_calendar_days"] == 5  # Dec 5 to Dec 9
    assert w_last["period_role"] == "EXCLUDED_BOUNDARY_END"


def test_zero_transaction_weeks_semantics(calendar_audit):
    """Verify weeks with zero transactions are NOT marked as partial observation weeks."""
    zero_weeks = calendar_audit[calendar_audit["is_zero_transaction_week"] == True]
    assert len(zero_weeks) == 2
    assert set(zero_weeks["week_start"].dt.strftime("%Y-%m-%d")) == {"2009-12-28", "2010-12-27"}
    
    for _, w in zero_weeks.iterrows():
        # Crucial semantic rule: zero demand does not mean partial observation
        assert w["is_partial_observation_week"] == False
        assert w["store_closure_status"] == "possible_closure"
        assert w["scoring_eligibility"] == "ELIGIBLE_FULL_WEEK"
        assert w["transaction_count"] == 0
        delta = pd.to_datetime(w["week_end_exclusive"]) - pd.to_datetime(w["week_start"])
        assert delta == pd.Timedelta(days=7)


def test_weekly_bin_interval_semantics(calendar_audit):
    """Verify interval [week_start, week_end_exclusive) spans exactly 7 calendar days."""
    for _, row in calendar_audit.iterrows():
        delta = row["week_end_exclusive"] - row["week_start"]
        assert delta == pd.Timedelta(days=7)
        # Week starts must be Monday (dayofweek == 0)
        assert row["week_start"].dayofweek == 0
        # Week ends must be Monday (dayofweek == 0)
        assert row["week_end_exclusive"].dayofweek == 0


def test_boundary_timestamp_exact_assignment():
    """Verify exact timestamp binning for boundary cases."""
    # Sunday evening at 23:59:59.999 belongs to the week starting the prior Monday
    sun_ts = pd.Timestamp("2010-12-05 23:59:59.999999")
    sun_week = sun_ts.floor("D") - pd.to_timedelta(sun_ts.dayofweek, unit="D")
    assert sun_week == pd.Timestamp("2010-11-29")
    
    # Monday morning at 00:00:00 belongs to the new week
    mon_ts = pd.Timestamp("2010-12-06 00:00:00.000000")
    mon_week = mon_ts.floor("D") - pd.to_timedelta(mon_ts.dayofweek, unit="D")
    assert mon_week == pd.Timestamp("2010-12-06")
    
    # Tuesday morning belongs to the same Monday week
    tue_ts = pd.Timestamp("2010-12-07 10:15:30")
    tue_week = tue_ts.floor("D") - pd.to_timedelta(tue_ts.dayofweek, unit="D")
    assert tue_week == pd.Timestamp("2010-12-06")
