"""
Unit test verifying Time-Series Expanding Window CV Indexing and Slicing.
Audits Gate G06 and prevents IndexError: positional indexers are out-of-bounds.
"""
import pytest
import pandas as pd
import numpy as np
from src.split import chronological_split, expanding_window_cv


def test_cv_split_indexing_integrity():
    """
    Test that expanding_window_cv indices correctly slice train and validation subsets
    without throwing IndexError, even if the input DataFrame has non-standard or filtered index.
    """
    # Create synthetic panel with non-contiguous index
    dates = pd.date_range("2010-01-01", periods=50, freq="W-MON")
    skus = ["SKU_A", "SKU_B", "SKU_C"]
    
    records = []
    for d in dates:
        for s in skus:
            records.append({"week_start": d, "sku_id": s, "target": np.random.poisson(10)})
            
    df_full = pd.DataFrame(records)
    # Filter to simulate non-contiguous index
    df_filtered = df_full[df_full.index % 2 == 0].copy()
    assert list(df_filtered.index[:5]) != [0, 1, 2, 3, 4], "Synthetic index must be non-contiguous"
    
    # Run split
    df_trainval, df_test, split_info = chronological_split(df_filtered, test_weeks=8)
    
    # Must be able to generate folds
    folds = expanding_window_cv(df_trainval, n_folds=3, min_train_weeks=10)
    assert len(folds) >= 1, "Failed to create CV folds"
    
    for fold_num, (train_idx, val_idx, fold_info) in enumerate(folds, 1):
        # Test that slicing works with BOTH loc and iloc if reset_index is used
        # Slicing with .loc using the returned indices
        df_tr_loc = df_trainval.loc[train_idx]
        df_va_loc = df_trainval.loc[val_idx]
        
        assert len(df_tr_loc) == fold_info["train_rows"], "Train row count mismatch"
        assert len(df_va_loc) == fold_info["val_rows"], "Val row count mismatch"
        
        # Verify strict temporal chronology: max train date < min val date
        max_train_date = df_tr_loc["week_start"].max()
        min_val_date = df_va_loc["week_start"].min()
        assert max_train_date < min_val_date, f"Fold {fold_num} leakage: max train ({max_train_date}) >= min val ({min_val_date})"


if __name__ == "__main__":
    test_cv_split_indexing_integrity()
    print("All CV split indexing and temporal chronology tests passed successfully!")
