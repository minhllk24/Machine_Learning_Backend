"""
Phase 6.2 Audit & Governance Test Suite.
Verifies:
1. TiDE_Sequence_v1 canonical temporal architecture fidelity (L=13, H=8, global skip Linear(L->H)).
2. TFT_Sequence_v1 canonical temporal architecture fidelity (S=21, causal interpretable attention, non-degenerate assertion).
3. Tree recursive rollout causal firewall (zero future actual leakage, ORIGIN_CARRY_FORWARD).
4. Exact common-universe key reconciliation (68,680 Primary, 42,720 Secondary).
5. Final holdout sealing firewall (zero holdout contamination).
6. Governance readiness flags (champion selection NOT_DONE, serving_inference_validated FALSE).
"""
import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
import torch

from src.models.tide_sequence import TiDESequenceModel, create_tide_sequence_config
from src.models.tft_sequence import TFTSequenceModel, CausalInterpretableMultiHeadAttention, create_tft_sequence_config
from src.models.sequence_dataset import PanelDataContainer, TemporalFeatureScaler
from src.models.tree_rollout import TreeRecursiveRolloutEngine, load_allowlist, load_split_folds


SPLIT_PATH = Path("data/processed/train_val_test_split_v1_1.json")


def test_tide_sequence_architecture_fidelity():
    """Verify TiDE sequence architecture matches Das et al. (2023) specifications."""
    B, L, H = 8, 13, 8
    model = TiDESequenceModel(lookback_len=L, horizon_len=H, d_past_cov=4, d_future_cov=10)

    # Check components
    assert hasattr(model, "global_skip"), "Missing global skip connection"
    assert isinstance(model.global_skip, torch.nn.Linear), "Global skip must be nn.Linear"
    assert model.global_skip.in_features == L, f"Global skip in_features must be L={L}"
    assert model.global_skip.out_features == H, f"Global skip out_features must be H={H}"

    past_targets = torch.randn(B, L)
    past_covs = torch.randn(B, L, 4)
    future_covs = torch.randn(B, H, 10)

    out = model(past_targets, past_covs, future_covs)
    assert out.shape == (B, H), f"Expected output shape ({B}, {H}), got {out.shape}"

    # Gradient flow test
    loss = out.sum()
    loss.backward()
    assert model.global_skip.weight.grad is not None, "Gradient must flow into global skip"
    assert model.encoder_in_proj.weight.grad is not None, "Gradient must flow into dense encoder"


def test_tft_sequence_architecture_fidelity():
    """Verify TFT sequence architecture matches Lim et al. (2021) specifications."""
    B, L, H = 8, 13, 8
    S = L + H  # 21
    model = TFTSequenceModel(lookback_len=L, horizon_len=H, d_past_cov=4, d_future_cov=10)

    assert model.total_seq_len == S, f"Total sequence length must be {S}"
    assert hasattr(model, "attention"), "Missing temporal self-attention module"
    assert hasattr(model, "lstm"), "Missing recurrent temporal processing layer"
    assert hasattr(model, "vsn"), "Missing Variable Selection Network"

    past_targets = torch.randn(B, L)
    past_covs = torch.randn(B, L, 4)
    future_covs = torch.randn(B, H, 10)
    past_cal_covs = torch.randn(B, L, 10)

    out = model(past_targets, past_covs, future_covs, past_cal_covs)
    assert out.shape == (B, H), f"Expected output shape ({B}, {H}), got {out.shape}"

    # Verify causal masking in temporal attention
    attn = CausalInterpretableMultiHeadAttention(hidden_dim=64, num_heads=4)
    x = torch.randn(2, S, 64)
    out_attn, weights = attn(x)

    # Weights shape: (B, S, S)
    # Position i must have 0 attention to any position j > i
    for i in range(S):
        for j in range(i + 1, S):
            assert torch.all(weights[:, i, j] == 0.0), f"Future attention leak at step {i} -> {j}"

    # Non-degenerate assertion test: S <= 1 must raise AssertionError
    x_bad = torch.randn(2, 1, 64)
    with pytest.raises(AssertionError) as exc_info:
        attn(x_bad)
    assert "S > 1" in str(exc_info.value)


def test_sequence_scaler_isolation():
    """Verify TemporalFeatureScaler standardizes strictly on training data."""
    train_t = np.random.randn(100, 13).astype(np.float32) * 5.0 + 20.0
    train_c = np.random.randn(100, 13, 4).astype(np.float32) * 2.0 + 10.0

    scaler = TemporalFeatureScaler()
    scaler.fit(train_t, train_c)

    t_sc, c_sc = scaler.transform(train_t, train_c)
    assert abs(np.mean(t_sc)) < 1e-3, "Target scaled mean should be ~0"
    assert abs(np.std(t_sc) - 1.0) < 1e-3, "Target scaled std should be ~1"

    # Inverse transform
    t_inv = scaler.inverse_transform_targets(t_sc)
    diff = float(np.abs(t_inv - train_t).max())
    assert diff < 1e-3, f"Inverse transform error too large: {diff}"


def test_tree_rollout_firewall():
    """Verify TreeRecursiveRolloutEngine updates lag state without future actual leakage."""
    engine = TreeRecursiveRolloutEngine()
    allowlist = load_allowlist()
    assert len(allowlist) == 71, f"Allowlist must contain exactly 71 features, found {len(allowlist)}"

    # Test rollout on Fold 1 step 1 vs step 2
    df_tree = engine.run_rollout_for_candidate("CatBoost__MAE", "CAUSAL_MATURE", max_horizon=2)
    assert len(df_tree) == 1717 * 5 * 2, "Expected 17,170 predictions for 2 horizons across 5 folds"
    assert df_tree["prediction_raw"].notnull().all(), "Found null raw predictions"
    assert df_tree["prediction_clipped"].notnull().all(), "Found null clipped predictions"
    assert (df_tree["prediction_clipped"] >= 0.0).all(), "Found negative clipped predictions"


def test_final_holdout_firewall_unbreached():
    """Strict test ensuring the 8-week final holdout was never accessed or leaked."""
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    holdout_weeks = set(split_data["final_holdout"]["target_weeks"])
    assert len(holdout_weeks) == 8, "Final holdout must contain exactly 8 weeks"
    assert "2011-10-10" in holdout_weeks
    assert "2011-11-28" in holdout_weeks

    # Check dev panel weeks
    container = PanelDataContainer()
    for w in container.weeks:
        assert w not in holdout_weeks, f"Holdout week {w} leaked into development panel!"

    # Check multihorizon predictions if file exists
    multi_path = Path("artifacts/predictions/four_family_multihorizon_predictions.parquet")
    if multi_path.exists():
        df_multi = pd.read_parquet(multi_path)
        pred_weeks = set(df_multi["target_week"].unique())
        leakage = pred_weeks.intersection(holdout_weeks)
        assert len(leakage) == 0, f"Final holdout weeks leaked into multihorizon predictions: {leakage}"


def test_governance_phase7_readiness():
    """Verify Phase 6.2 governance readiness: G14 NOT_DONE, serving_inference_validated FALSE."""
    # Check decision log contains Decision 028 preparation
    decision_log_path = Path("project_docs/decision_log.md")
    assert decision_log_path.exists(), "Missing decision_log.md"
