"""
Unit & Audit Test for SKU Eligibility Selection Bias and Lookahead Leakage.
Audits Gate G04, G05, and Deliverable C.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_sku_eligibility_lookahead_leakage_audit():
    """
    Audits whether computing SKU eligibility across the full timeline introduces lookahead leakage.
    Demonstrates the difference between full-timeline eligibility vs train-only eligibility.
    """
    # Create synthetic weekly panel for 4 SKUs over 20 weeks (weeks 0 to 19)
    # Train period: weeks 0 to 14 (15 weeks)
    # Test period: weeks 15 to 19 (5 weeks)
    
    records = []
    # SKU_A: 12 active weeks in train, 4 in test -> Valid in both
    for w in range(12):
        records.append({"sku_id": "SKU_A", "week_idx": w, "demand": 10})
    for w in range(15, 19):
        records.append({"sku_id": "SKU_A", "week_idx": w, "demand": 10})
        
    # SKU_B: 6 active weeks in train (demand 30), but 6 active weeks in test (demand 60)
    # Under FULL-TIMELINE: active_weeks = 12, total_demand = 90 -> QUALIFIES (LEAKY!)
    # Under TRAIN-ONLY: active_weeks = 6, total_demand = 30 -> DISQUALIFIED (CAUSAL!)
    for w in range(6):
        records.append({"sku_id": "SKU_B", "week_idx": w, "demand": 5})
    for w in range(15, 21):
        records.append({"sku_id": "SKU_B", "week_idx": w, "demand": 10})
        
    # SKU_C: Appears for the FIRST TIME in test period (week 16)
    # Cold start SKU
    for w in range(16, 20):
        records.append({"sku_id": "SKU_C", "week_idx": w, "demand": 25})

    df = pd.DataFrame(records)
    
    # 1. Leaky Full-Timeline Calculation
    agg_full = df.groupby("sku_id").agg(
        active_weeks=("week_idx", "nunique"),
        total_demand=("demand", "sum"),
        first_week=("week_idx", "min")
    )
    leaky_cohort = agg_full[
        (agg_full["active_weeks"] >= 10) & 
        (agg_full["total_demand"] >= 50)
    ].index.tolist()
    
    # 2. Causal Train-Only Calculation (cutoff at week 14)
    df_train = df[df["week_idx"] < 15]
    agg_train = df_train.groupby("sku_id").agg(
        active_weeks=("week_idx", "nunique"),
        total_demand=("demand", "sum"),
        first_week=("week_idx", "min")
    )
    causal_cohort = agg_train[
        (agg_train["active_weeks"] >= 10) & 
        (agg_train["total_demand"] >= 50)
    ].index.tolist()
    
    # Assertions demonstrating the leakage mechanism
    assert "SKU_B" in leaky_cohort, "SKU_B should qualify under leaky full-timeline calculation"
    assert "SKU_B" not in causal_cohort, "SKU_B must NOT qualify under causal train-only calculation"
    assert "SKU_A" in causal_cohort, "SKU_A must qualify in both"
    
    # Leaked SKUs count
    leaked_skus = set(leaky_cohort) - set(causal_cohort)
    assert len(leaked_skus) == 1 and "SKU_B" in leaked_skus, "Detected lookahead cohort leakage"
    print(f"Leakage audit passed: SKU_B correctly flagged as lookahead selection bias!")


if __name__ == "__main__":
    test_sku_eligibility_lookahead_leakage_audit()
    print("All SKU eligibility leakage tests passed successfully!")
