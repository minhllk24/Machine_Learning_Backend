"""
Automated tests for split manifest v1.1 and final-test firewall.
Verifies:
- Split chronology and fold non-overlap.
- Horizon alignment (target_week = feature_origin_week + 7 calendar days).
- Final holdout strict isolation (never appears in train/validation folds).
- Final holdout completeness (all 8 target weeks are 100% complete weeks).
- Deterministic split reconstruction.
"""
import json
from pathlib import Path
import pandas as pd
import pytest
from src.config import TRAIN_VAL_TEST_SPLIT_V1_1, CALENDAR_WEEK_AUDIT
from src.split import generate_calendar_split_manifest


@pytest.fixture
def manifest():
    assert TRAIN_VAL_TEST_SPLIT_V1_1.exists(), f"Missing {TRAIN_VAL_TEST_SPLIT_V1_1}"
    with open(TRAIN_VAL_TEST_SPLIT_V1_1, "r", encoding="utf-8") as f:
        return json.load(f)


def test_split_chronology_and_non_overlap(manifest):
    """Verify that expanding CV folds are strictly chronological and train/val never overlap."""
    folds = manifest["cv_folds"]
    assert len(folds) == 5
    
    prev_train_weeks = 0
    for fold in folds:
        train_weeks = fold["train_target_weeks"]
        val_weeks = fold["val_target_weeks"]
        
        # 1. Train set must strictly expand
        assert len(train_weeks) > prev_train_weeks
        prev_train_weeks = len(train_weeks)
        
        # 2. Train and Val must have ZERO overlap
        overlap = set(train_weeks).intersection(set(val_weeks))
        assert len(overlap) == 0, f"Found fold {fold['fold_id']} train/val overlap: {overlap}"
        
        # 3. Validation must strictly follow training chronologically
        train_end = pd.Timestamp(fold["train_target_end"])
        val_start = pd.Timestamp(fold["val_target_start"])
        assert val_start > train_end, f"Fold {fold['fold_id']} validation started before train end!"


def test_horizon_alignment(manifest):
    """Verify target_week is exactly 7 calendar days after feature_origin_week for horizon h=1."""
    steps = manifest["forecast_steps"]
    assert len(steps) == 105  # 105 steps across 106 weeks
    
    for step in steps:
        origin = pd.Timestamp(step["feature_origin_week"])
        target = pd.Timestamp(step["target_week"])
        assert target - origin == pd.Timedelta(days=7), (
            f"Step {step['step_id']} misaligned: origin={origin}, target={target}"
        )


def test_final_holdout_isolation(manifest):
    """Verify final holdout target weeks NEVER appear in any train or validation fold."""
    holdout_targets = set(manifest["final_holdout"]["target_weeks"])
    assert len(holdout_targets) == 8
    
    for fold in manifest["cv_folds"]:
        train_leak = holdout_targets.intersection(set(fold["train_target_weeks"]))
        assert len(train_leak) == 0, f"Holdout leak into fold {fold['fold_id']} train: {train_leak}"
        
        val_leak = holdout_targets.intersection(set(fold["val_target_weeks"]))
        assert len(val_leak) == 0, f"Holdout leak into fold {fold['fold_id']} validation: {val_leak}"


def test_holdout_completeness(manifest):
    """Verify all 8 holdout target weeks are 100% complete calendar weeks."""
    cal_df = pd.read_csv(CALENDAR_WEEK_AUDIT)
    holdout_targets = manifest["final_holdout"]["target_weeks"]
    
    for tw in holdout_targets:
        row = cal_df[cal_df["week_start"] == tw].iloc[0]
        assert row["is_partial_observation_week"] == False, f"Holdout target week {tw} is a partial observation week!"
        assert row["scoring_eligibility"] == "ELIGIBLE_FULL_WEEK", f"Holdout target week {tw} not eligible!"
        assert row["observed_calendar_days"] >= 5, f"Holdout target week {tw} has low observed days: {row['observed_calendar_days']}"
        assert row["period_role"] == "FINAL_HOLDOUT"


def test_deterministic_split_reconstruction():
    """Verify generating split manifest twice produces identical JSON payloads."""
    m1 = generate_calendar_split_manifest()
    m2 = generate_calendar_split_manifest()
    assert m1 == m2, "Split manifests differed between successive generations!"
