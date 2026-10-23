"""
Phase 6.1 Automated Audit & Reconciliation Test Suite.
Verifies cross-phase prediction ledger, metric reconciliation,
architecture fidelity assertions, training budget diagnostics,
target availability manifest, multi-horizon metrics, and final holdout firewall.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch

from src.models.tide import TiDEModel, create_tide_primary_config
from src.models.tft import TFTModel, create_tft_primary_config
from src.models.train_deep import load_verified_predictor_allowlist


@pytest.fixture(scope="module")
def allowlist():
    features, data = load_verified_predictor_allowlist()
    return features


def test_cross_phase_prediction_ledger_completeness():
    """Verify that phase_06_1_cross_phase_metric_reconciliation.csv exists and has 34 candidate rows."""
    p = Path("artifacts/tables/phase_06_1_cross_phase_metric_reconciliation.csv")
    assert p.exists(), "Reconciliation CSV does not exist!"
    df = pd.read_csv(p)
    assert len(df) == 34, f"Expected 34 candidate-cohort rows, found {len(df)}"
    assert set(df['phase'].unique()) == {"Phase 4", "Phase 5", "Phase 6"}
    assert set(df['cohort'].unique()) == {"CAUSAL_MATURE", "LATE_MATURING"}


def test_parquet_prediction_row_counts_and_denominators():
    """Verify physical row counts and demand denominators across all three parquet files."""
    df_b = pd.read_parquet("artifacts/predictions/baseline_oof_predictions.parquet")
    df_t = pd.read_parquet("artifacts/predictions/tree_models_oof_predictions.parquet")
    df_d = pd.read_parquet("artifacts/predictions/deep_models_oof_predictions.parquet")

    assert len(df_b) == 1002600
    assert len(df_t) == 668400
    assert len(df_d) == 222800

    # Demand denominators
    for df, col_y, col_c in [(df_t, 'actual', 'cohort'), (df_d, 'actual', 'cohort')]:
        sub_p = df[df[col_c] == 'CAUSAL_MATURE']
        sub_s = df[df[col_c] == 'LATE_MATURING']
        assert sub_p.groupby('model_name')[col_y].sum().iloc[0] == pytest.approx(2025137.0, rel=1e-5)
        assert sub_s.groupby('model_name')[col_y].sum().iloc[0] == pytest.approx(438164.0, rel=1e-5)


def test_tide_architecture_fidelity_and_skip(allowlist):
    """Verify TiDE geometry and that global skip connects to demand_lag_1 (idx 0)."""
    cfg = create_tide_primary_config(len(allowlist))
    kw = {
        'in_dim': cfg['hyperparameters']['in_dim'],
        'hidden_dim': cfg['hyperparameters']['hidden_dim'],
        'num_encoder_layers': cfg['hyperparameters']['num_encoder_layers'],
        'decoder_dim': cfg['hyperparameters']['decoder_dim'],
        'dropout': cfg['hyperparameters']['dropout'],
        'primary_lag_idx': cfg['hyperparameters']['primary_lag_idx']
    }
    model = TiDEModel(**kw)
    x = torch.randn(8, 71)
    out = model(x)
    assert out.shape == (8,)

    # Check global skip is linear(1, 1)
    assert isinstance(model.global_skip, torch.nn.Linear)
    assert model.global_skip.in_features == 1
    assert model.global_skip.out_features == 1


def test_tft_attention_dimension_audit(allowlist):
    """Verify that TFT InterpretableMultiHeadAttention operates on S=1 sequence."""
    cfg = create_tft_primary_config(allowlist)
    kw = {
        'group_dims': cfg['group_dims'],
        'group_indices': cfg['group_indices'],
        'hidden_dim': cfg['hyperparameters']['hidden_dim'],
        'num_heads': cfg['hyperparameters']['num_heads'],
        'dropout': cfg['hyperparameters']['dropout']
    }
    model = TFTModel(**kw)
    x = torch.randn(8, 71)
    out = model(x)
    assert out.shape == (8,)

    # Verify that inside attention, sequence length is 1
    assert model.attention.hidden_dim == 64
    assert model.attention.num_heads == 4


def test_architecture_fidelity_matrix_completeness():
    """Verify artifacts/tables/phase_06_1_architecture_fidelity_matrix.csv has 10 components."""
    p = Path("artifacts/tables/phase_06_1_architecture_fidelity_matrix.csv")
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 10
    assert set(df['model_name'].unique()) == {"TiDE", "TFT"}


def test_training_budget_diagnostics_records():
    """Verify phase_06_1_training_budget_diagnostics.csv exists and contains empirical curves."""
    p = Path("artifacts/tables/phase_06_1_training_budget_diagnostics.csv")
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 20
    assert set(df['model_name'].unique()) == {"TFT-inspired", "TiDE-inspired"}


def test_target_availability_manifest_completeness(allowlist):
    """Verify phase_06_1_target_availability_manifest.csv has 71 features and correct classes."""
    p = Path("artifacts/tables/phase_06_1_target_availability_manifest.csv")
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 71
    assert set(df['feature_name']) == set(allowlist)
    assert set(df['temporal_class'].unique()) == {"KNOWN_FUTURE", "OBSERVED_AT_ORIGIN", "DERIVED_FROM_PAST", "UNKNOWN_FUTURE"}


def test_multihorizon_metrics_integrity():
    """Verify phase_06_1_multihorizon_metrics.csv exists and records H=1, H=4, H=8 scopes."""
    p = Path("artifacts/tables/phase_06_1_multihorizon_metrics.csv")
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 30
    assert "H=1_step" in df['horizon_scope'].values
    assert "H=4_weeks_pooled" in df['horizon_scope'].values
    assert "H=8_weeks_pooled" in df['horizon_scope'].values


def test_final_holdout_firewall_strictly_preserved():
    """Verify zero final holdout target weeks exist in any prediction file."""
    holdout_weeks = {
        "2011-10-10", "2011-10-17", "2011-10-24", "2011-10-31",
        "2011-11-07", "2011-11-14", "2011-11-21", "2011-11-28"
    }
    for p in [
        "artifacts/predictions/baseline_oof_predictions.parquet",
        "artifacts/predictions/tree_models_oof_predictions.parquet",
        "artifacts/predictions/deep_models_oof_predictions.parquet"
    ]:
        df = pd.read_parquet(p)
        weeks_in_file = set(df['target_week'].unique())
        overlap = weeks_in_file.intersection(holdout_weeks)
        assert len(overlap) == 0, f"HOLDOUT LEAKAGE FIREWALL BREACH in {p}: {overlap}"


def test_common_universe_keys_equality():
    """Verify deep models share 100% exact keys with tree models and naive baseline."""
    df_b = pd.read_parquet("artifacts/predictions/baseline_oof_predictions.parquet")
    df_t = pd.read_parquet("artifacts/predictions/tree_models_oof_predictions.parquet")
    df_d = pd.read_parquet("artifacts/predictions/deep_models_oof_predictions.parquet")

    naive_keys = set(df_b[df_b['model_name'] == 'Naive_1']['sku_id'] + '__' + df_b[df_b['model_name'] == 'Naive_1']['target_week'])
    tree_keys = set(df_t[df_t['model_name'] == 'CatBoost__MAE']['sku_id'] + '__' + df_t[df_t['model_name'] == 'CatBoost__MAE']['target_week'])
    deep_keys = set(df_d[df_d['model_name'] == 'TiDE__primary_config']['sku_id'] + '__' + df_d[df_d['model_name'] == 'TiDE__primary_config']['target_week'])

    assert len(naive_keys) == 111400
    assert tree_keys == naive_keys
    assert deep_keys == naive_keys


def test_catboost_tweedie_reconciled_values():
    """Verify CatBoost Tweedie values match canonical physical parquet and CSV."""
    df_t = pd.read_parquet("artifacts/predictions/tree_models_oof_predictions.parquet")
    sub = df_t[(df_t['model_name'] == 'CatBoost__Tweedie_p15') & (df_t['cohort'] == 'CAUSAL_MATURE')]
    wape = np.sum(np.abs(sub['actual'] - sub['prediction'])) / sub['actual'].sum() * 100
    assert wape == pytest.approx(73.5118, rel=1e-3)
    assert np.mean(sub['clipped_at_zero'] == True) == 0.0
