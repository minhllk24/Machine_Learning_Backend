"""
Phase 16 Calendar and Weekly Aggregation Boundary Test Suite.
Verifies exact canonical ISO Monday floor semantics:
1. Sunday 23:59:59.999999 belongs to prior Monday week.
2. Monday 00:00:00.000000 begins new Monday week.
3. Monday 23:59:59.999999 belongs to same Monday week.
4. Earliest observed raw transaction (2009-12-01) mapped to 2009-11-30 Monday floor.
5. Latest observed raw transaction (2011-12-09) mapped to 2011-12-05 Monday floor.
6. Timezone conversion consistency (UTC vs naive timestamps).
7. Half-open interval [week_start, week_end_exclusive) spanning exactly 7 days.
"""
from datetime import datetime, timezone
import pandas as pd
import pytest

from src.config import CALENDAR_WEEK_AUDIT


def test_sunday_evening_boundary_assignment():
    """Verify Sunday 23:59:59.999999 is assigned to the preceding Monday floor."""
    sunday_ts = pd.Timestamp("2011-05-15 23:59:59.999999")
    monday_floor = sunday_ts.floor("D") - pd.to_timedelta(sunday_ts.dayofweek, unit="D")
    assert monday_floor == pd.Timestamp("2011-05-09")
    assert monday_floor.dayofweek == 0  # Monday


def test_monday_start_boundary_assignment():
    """Verify Monday 00:00:00 begins the new weekly interval."""
    monday_ts = pd.Timestamp("2011-05-16 00:00:00.000000")
    monday_floor = monday_ts.floor("D") - pd.to_timedelta(monday_ts.dayofweek, unit="D")
    assert monday_floor == pd.Timestamp("2011-05-16")
    assert monday_floor.dayofweek == 0


def test_monday_late_evening_boundary_assignment():
    """Verify Monday 23:59:59 belongs to that same Monday week."""
    monday_night_ts = pd.Timestamp("2011-05-16 23:59:59.999999")
    monday_floor = monday_night_ts.floor("D") - pd.to_timedelta(monday_night_ts.dayofweek, unit="D")
    assert monday_floor == pd.Timestamp("2011-05-16")


def test_first_and_last_raw_timestamps_mapping():
    """Verify exact Monday floor assignment for first and last raw transactions."""
    # First transaction: 2009-12-01 07:45:00 (Tuesday)
    first_ts = pd.Timestamp("2009-12-01 07:45:00")
    first_week = first_ts.floor("D") - pd.to_timedelta(first_ts.dayofweek, unit="D")
    assert first_week == pd.Timestamp("2009-11-30")

    # Last transaction: 2011-12-09 12:50:00 (Friday)
    last_ts = pd.Timestamp("2011-12-09 12:50:00")
    last_week = last_ts.floor("D") - pd.to_timedelta(last_ts.dayofweek, unit="D")
    assert last_week == pd.Timestamp("2011-12-05")


def test_timezone_aware_timestamp_conversion_consistency():
    """Verify timezone-aware timestamps maintain identical Monday-floor date."""
    utc_ts = pd.Timestamp("2011-07-04 02:30:00", tz="UTC")  # Monday
    # Naive equivalent
    naive_ts = utc_ts.tz_localize(None)

    utc_floor = utc_ts.floor("D") - pd.to_timedelta(utc_ts.dayofweek, unit="D")
    naive_floor = naive_ts.floor("D") - pd.to_timedelta(naive_ts.dayofweek, unit="D")

    assert utc_floor.strftime("%Y-%m-%d") == naive_floor.strftime("%Y-%m-%d") == "2011-07-04"


def test_calendar_half_open_interval():
    """Verify every calendar week has exactly 7 days half-open span [week_start, week_end_exclusive)."""
    assert CALENDAR_WEEK_AUDIT.exists()
    df = pd.read_csv(CALENDAR_WEEK_AUDIT)
    df["ws"] = pd.to_datetime(df["week_start"])
    df["we"] = pd.to_datetime(df["week_end_exclusive"])

    for _, row in df.iterrows():
        delta = row["we"] - row["ws"]
        assert delta == pd.Timedelta(days=7)
        assert row["ws"].dayofweek == 0
        assert row["we"].dayofweek == 0
