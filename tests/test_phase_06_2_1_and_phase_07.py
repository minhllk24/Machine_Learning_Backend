"""
Unit and Audit Tests for Phase 6.2.1 Acceptance Remediation and Phase 7 Champion Refit.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import torch
from catboost import CatBoostRegressor

from src.models.tide_sequence import TiDESequenceModel
from src.models.tft_sequence import TFTSequenceModel


def test_candidate_stream_inventory_count_and_keys():
    """Verify that four_family_multihorizon_predictions contains exactly 11 candidate streams and 1,225,400 rows."""
    p = Path("artifacts/predictions/four_family_multihorizon_predictions.parquet")
    assert p.exists(), f"Parquet file not found: {p}"
    df = pd.read_parquet(p)
    
    assert len(df) == 1225400, f"Expected 1,225,400 records, got {len(df)}"
    assert df["model_name"].nunique() == 11, f"Expected 11 unique models, got {df['model_name'].nunique()}"
    
    expected_models = {
        "Naive_1", "MA_4", "MA_8", "SeasonalNaive_52", "Zero_Demand",
        "LightGBM__regression_l1", "LightGBM__tweedie_p15",
        "CatBoost__MAE", "CatBoost__Tweedie_p15",
        "TiDE_Sequence_v1", "TFT_Sequence_v1"
    }
    assert set(df["model_name"].unique()) == expected_models


def test_clipping_semantics_decomposition():
    """Verify clipping semantics: baselines must have 0% true clipping, and final zeros must be distinguished."""
    clip_path = Path("artifacts/tables/phase_06_2_1_clipping_semantics_audit.csv")
    assert clip_path.exists(), f"File not found: {clip_path}"
    df_clip = pd.read_csv(clip_path)

    # Baselines should have 0% clipping
    base_rows = df_clip[df_clip["model_family"] == "Statistical_Baseline"]
    assert np.all(base_rows["clipped_at_zero_pct"] == 0.0), "Baselines must have 0% clipping!"
    assert np.all(base_rows["raw_negative_pct"] == 0.0), "Baselines must have 0% raw negative!"

    # Zero_Demand has 100% final zero, but 0% clipping
    zd = df_clip[df_clip["model_name"] == "Zero_Demand"]
    assert np.all(zd["final_zero_pct"] == 100.0)
    assert np.all(zd["clipped_at_zero_pct"] == 0.0)


def test_feature_availability_audit_completeness():
    """Verify that all feature channels are approved and have valid lineage without synthetic promotions."""
    feat_path = Path("artifacts/tables/phase_06_2_1_feature_availability_audit.csv")
    assert feat_path.exists(), f"File not found: {feat_path}"
    df_feat = pd.read_csv(feat_path)
    
    assert len(df_feat) >= 14
    assert np.all(df_feat["status"] == "APPROVED")
    # Verify no synthetic discount feature is present
    feat_names = df_feat["feature_name"].tolist()
    assert "discount_depth" not in feat_names
    assert "promo_flag" not in feat_names


def test_causal_temporal_perturbation_invariance():
    """Verify that future calendar covariates affect outputs, but models never accept future actual demand."""
    tft = TFTSequenceModel(13, 8, 4, 10, hidden_dim=32, num_heads=2)
    tft.eval()
    
    B, L, H = 2, 13, 8
    p_tgt = torch.randn(B, L)
    p_cov = torch.randn(B, L, 4)
    f_cal_1 = torch.randn(B, H, 10)
    f_cal_2 = f_cal_1 + 5.0
    p_cal = torch.randn(B, L, 10)
    
    with torch.no_grad():
        out_1 = tft(p_tgt, p_cov, f_cal_1, p_cal)
        out_2 = tft(p_tgt, p_cov, f_cal_2, p_cal)
    
    assert out_1.shape == (B, H)
    assert torch.all(torch.isfinite(out_1))
    # Must be sensitive to future calendar
    assert (out_1 - out_2).abs().max().item() > 1e-4


def test_champion_refit_artifacts_exist_and_loadable():
    """Verify all 6 production candidate models exist, are loadable, and output finite predictions."""
    prod_dir = Path("artifacts/models/production_candidates")
    assert prod_dir.exists()

    expected_files = [
        "CatBoost__MAE_champion_CAUSAL_MATURE.cbm",
        "CatBoost__MAE_champion_LATE_MATURING.cbm",
        "CatBoost__Tweedie_p15_champion_CAUSAL_MATURE.cbm",
        "CatBoost__Tweedie_p15_champion_LATE_MATURING.cbm",
        "TiDE_Sequence_v1_champion_CAUSAL_MATURE.pt",
        "TiDE_Sequence_v1_champion_LATE_MATURING.pt",
        "champion_refit_manifest.json"
    ]
    for fn in expected_files:
        fp = prod_dir / fn
        assert fp.exists(), f"Missing production candidate file: {fp}"
        assert fp.stat().st_size > 0, f"Empty file: {fp}"

    # Load CatBoost champion
    cb = CatBoostRegressor()
    cb.load_model(str(prod_dir / "CatBoost__MAE_champion_CAUSAL_MATURE.cbm"))
    dummy_x = np.random.randn(5, 71)
    preds = cb.predict(dummy_x)
    assert len(preds) == 5
    assert np.all(np.isfinite(preds))

    # Load TiDE champion
    ckpt = torch.load(prod_dir / "TiDE_Sequence_v1_champion_CAUSAL_MATURE.pt", map_location="cpu", weights_only=False)
    assert "state_dict" in ckpt
    assert "scaler_target_mean" in ckpt
    tide = TiDESequenceModel(13, 8, 4, 10, 16, 64, 2, 64, 0.1)
    tide.load_state_dict(ckpt["state_dict"])
    tide.eval()
    with torch.no_grad():
        t_out = tide(torch.randn(2, 13), torch.randn(2, 13, 4), torch.randn(2, 8, 10))
    assert t_out.shape == (2, 8)
    assert np.all(np.isfinite(t_out.numpy()))


def test_champion_refit_manifest_and_gate_g14():
    """Verify champion_refit_manifest.json metadata and Gate G14 PASS state."""
    manifest_path = Path("artifacts/models/production_candidates/champion_refit_manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    
    assert m["governing_gate"] == "G14_PASS"
    assert m["primary_champion"] == "CatBoost__MAE"
    assert m["volume_risk_challenger"] == "CatBoost__Tweedie_p15"
    assert m["deep_sequence_alternative"] == "TiDE_Sequence_v1"
    assert m["serving_inference_validated"] is False
    assert m["multi_week_inference_validated"] is False
    assert len(m["models"]) == 6

    # Verify Gate Report has G14 as PASS
    gate_path = Path("project_docs/gate_report.md")
    gate_text = gate_path.read_text(encoding="utf-8")
    assert "| **G14** | Model selection freeze | **PASS** |" in gate_text


def test_holdout_firewall_strictly_unbreached():
    """Verify that zero rows with target_week >= 2011-10-10 exist in predictions or dev pool."""
    dev_path = Path("data/processed/sku_week_features_v1_2_dev.parquet")
    df_dev = pd.read_parquet(dev_path)
    assert not any(df_dev["target_week"] >= "2011-10-10"), "Holdout leak in dev pool!"

    multi_path = Path("artifacts/predictions/four_family_multihorizon_predictions.parquet")
    df_multi = pd.read_parquet(multi_path)
    assert not any(df_multi["target_week"] >= "2011-10-10"), "Holdout leak in multi-horizon predictions!"
