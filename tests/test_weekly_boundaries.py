"""
Unit tests for Weekly Boundary Bins, W-MON semantics, and Partial Week Detection.
Audits Gate G04 and Deliverable D.
"""
import pytest
import pandas as pd
from datetime import datetime


def test_pandas_weekly_frequency_semantics():
    """
    Clarifies the exact mathematical meaning of 'W-MON' vs 'W-SUN' in Pandas.
    In Pandas, the suffix represents the END day of the week, NOT the start day!
    - 'W-MON' = Week ending on Monday (Start: Tuesday, End: Monday).
    - 'W-SUN' = Week ending on Sunday (Start: Monday, End: Sunday).
    """
    # Sample timestamps spanning Sunday, Monday, Tuesday
    t_sunday = pd.Timestamp("2010-01-03 14:30:00")   # Sunday
    t_monday = pd.Timestamp("2010-01-04 09:15:00")   # Monday
    t_tuesday = pd.Timestamp("2010-01-05 11:00:00")  # Tuesday
    
    # Under W-MON:
    p_sun_mon = t_sunday.to_period("W-MON")
    p_mon_mon = t_monday.to_period("W-MON")
    p_tue_mon = t_tuesday.to_period("W-MON")
    
    # Sunday and Monday fall in the SAME period ending on Monday
    assert p_sun_mon == p_mon_mon, "Under W-MON, Sunday and Monday must be in the same period"
    # Tuesday starts a NEW period
    assert p_mon_mon != p_tue_mon, "Under W-MON, Tuesday must start a new period"
    assert p_mon_mon.start_time.day_name() == "Tuesday", "W-MON period starts on Tuesday!"
    assert p_mon_mon.end_time.day_name() == "Monday", "W-MON period ends on Monday!"

    # Under W-SUN (Business standard: Monday to Sunday):
    p_sun_sun = t_sunday.to_period("W-SUN")
    p_mon_sun = t_monday.to_period("W-SUN")
    p_tue_sun = t_tuesday.to_period("W-SUN")
    
    # Sunday is the END of the previous week
    assert p_sun_sun != p_mon_sun, "Under W-SUN, Sunday and Monday are in different weeks"
    # Monday and Tuesday are in the SAME week
    assert p_mon_sun == p_tue_sun, "Under W-SUN, Monday and Tuesday are in the same week"
    assert p_mon_sun.start_time.day_name() == "Monday", "W-SUN period starts on Monday!"
    assert p_mon_sun.end_time.day_name() == "Sunday", "W-SUN period ends on Sunday!"


def test_final_week_partial_detection():
    """
    Verify whether the final week of Online Retail II is a full or partial week.
    Dataset ends at 2011-12-09 12:50:00 (Friday).
    """
    final_timestamp = pd.Timestamp("2011-12-09 12:50:00")
    assert final_timestamp.day_name() == "Friday", "Final dataset date must be a Friday"
    
    # Standard Monday-Sunday business week:
    week_start = final_timestamp.floor("D") - pd.to_timedelta(final_timestamp.dayofweek, unit="D")
    week_end = week_start + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    assert week_start == pd.Timestamp("2011-12-05 00:00:00"), "Final week starts on Monday 2011-12-05"
    assert week_end == pd.Timestamp("2011-12-11 23:59:59"), "Final week ends on Sunday 2011-12-11"
    
    # Days present in data for final week: Mon 5, Tue 6, Wed 7, Thu 8, Fri 9 (5 days out of 7)
    days_present = (final_timestamp.dayofweek + 1)
    assert days_present == 5, "Final week contains only 5 business days (Mon-Fri) - it is a partial week!"


if __name__ == "__main__":
    test_pandas_weekly_frequency_semantics()
    test_final_week_partial_detection()
    print("All weekly boundary tests passed successfully!")
