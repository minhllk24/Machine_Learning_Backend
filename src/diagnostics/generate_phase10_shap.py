"""
Phase 10 — CatBoost SHAP Explainability Engine.
Computes TreeExplainer SHAP values, feature importance rankings,
dependence relationships, local case attributions, and checks mathematical additivity.

Inputs:
- artifacts/models/production_candidates/CatBoost__MAE_champion_CAUSAL_MATURE.cbm
- artifacts/models/production_candidates/CatBoost__MAE_champion_LATE_MATURING.cbm
- data/processed/sku_week_features_v1_2_dev.parquet
- data/processed/predictor_allowlist_v1_2.json

Outputs:
- artifacts/tables/phase_10_shap_global_importance.csv
- artifacts/tables/phase_10_shap_local_examples.csv
- artifacts/figures/phase_10_shap_summary.png
- artifacts/figures/phase_10_shap_dependence_top_features.png
- artifacts/figures/phase_10_shap_local_cases.png
- project_docs/phase_10_explainability_report.md
"""

import sys
import os
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
from catboost import CatBoostRegressor, Pool

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"

MODELS_DIR = PROJECT_ROOT / "artifacts/models/production_candidates"
FEATURES_PATH = PROJECT_ROOT / "data/processed/sku_week_features_v1_2_dev.parquet"
ALLOWLIST_PATH = PROJECT_ROOT / "data/processed/predictor_allowlist_v1_2.json"
TABLES_DIR = PROJECT_ROOT / "artifacts/tables"
FIGURES_DIR = PROJECT_ROOT / "artifacts/figures"
DOCS_DIR = PROJECT_ROOT / "project_docs"

os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

FEATURE_FAMILY_MAP = {
    "lag": "Lags (Recent Historical Demand)",
    "roll": "Rolling Aggregations (Moving Windows)",
    "ewm": "Exponentially Weighted Moving Averages",
    "momentum": "Momentum & Acceleration Indicators",
    "expanding": "Expanding Lifecycle Statistics",
    "price": "Price Dynamics & Relative Levels",
    "activity": "Transaction & Intermittency Counts",
    "calendar": "Calendar & Holiday Signals",
    "sin": "Calendar & Holiday Signals",
    "cos": "Calendar & Holiday Signals",
    "q4": "Calendar & Holiday Signals",
    "december": "Calendar & Holiday Signals",
    "christmas": "Calendar & Holiday Signals"
}

def get_feature_family(fname: str) -> str:
    fname_lower = fname.lower()
    for k, fam in FEATURE_FAMILY_MAP.items():
        if k in fname_lower:
            return fam
    return "Other Engineered Features"

def main():
    print("=" * 80)
    print("PHASE 10: CATBOOST SHAP EXPLAINABILITY ENGINE")
    print("=" * 80)

    # 1. Load allowlist and dev features
    print("1. Loading 71-feature allowlist and development pool features...")
    with open(ALLOWLIST_PATH, "r", encoding="utf-8") as f:
        allowlist = json.load(f)["allowed_predictor_names"]
    assert len(allowlist) == 71, f"Expected 71 features, got {len(allowlist)}"
    print(f"Allowlist verified: {len(allowlist)} predictors.")

    df_dev = pd.read_parquet(FEATURES_PATH)
    print(f"Loaded development pool features: {df_dev.shape}")

    # 2. Analyze Primary Cohort (CAUSAL_MATURE)
    print("\n2. Computing SHAP for Primary Champion (CAUSAL_MATURE)...")
    pri_model_path = MODELS_DIR / "CatBoost__MAE_champion_CAUSAL_MATURE.cbm"
    model_pri = CatBoostRegressor()
    model_pri.load_model(str(pri_model_path))

    df_pri_pool = df_dev[df_dev["cohort_tier"] == "CAUSAL_MATURE"]
    # Deterministic background sample of 3,000 observations
    sample_pri = df_pri_pool.sample(n=3000, random_state=42)
    X_pri = sample_pri[allowlist]

    pool_pri = Pool(X_pri)
    # Native CatBoost TreeExplainer ShapValues: returns (N, M+1) matrix
    shap_matrix_pri = model_pri.get_feature_importance(pool_pri, type="ShapValues")
    shap_vals_pri = shap_matrix_pri[:, :-1]
    base_val_pri = float(shap_matrix_pri[0, -1])

    # Additivity Verification
    preds_pri = model_pri.predict(X_pri)
    reconstructed_preds = np.sum(shap_vals_pri, axis=1) + base_val_pri
    max_additivity_diff = float(np.max(np.abs(preds_pri - reconstructed_preds)))
    print(f"Primary Base Value (Expected Model Output): {base_val_pri:.4f}")
    print(f"Primary Maximum Additivity Discrepancy: {max_additivity_diff:.2e} (Pass < 1e-10)")
    assert max_additivity_diff < 1e-8, "Additivity check failed for Primary model!"

    # 3. Analyze Secondary Cohort (LATE_MATURING)
    print("\n3. Computing SHAP for Secondary Champion (LATE_MATURING)...")
    sec_model_path = MODELS_DIR / "CatBoost__MAE_champion_LATE_MATURING.cbm"
    model_sec = CatBoostRegressor()
    model_sec.load_model(str(sec_model_path))

    df_sec_pool = df_dev[df_dev["cohort_tier"] == "LATE_MATURING"]
    sample_sec = df_sec_pool.sample(n=2000, random_state=42)
    X_sec = sample_sec[allowlist]

    pool_sec = Pool(X_sec)
    shap_matrix_sec = model_sec.get_feature_importance(pool_sec, type="ShapValues")
    shap_vals_sec = shap_matrix_sec[:, :-1]
    base_val_sec = float(shap_matrix_sec[0, -1])

    preds_sec = model_sec.predict(X_sec)
    max_additivity_sec = float(np.max(np.abs(preds_sec - (np.sum(shap_vals_sec, axis=1) + base_val_sec))))
    print(f"Secondary Base Value: {base_val_sec:.4f}")
    print(f"Secondary Maximum Additivity Discrepancy: {max_additivity_sec:.2e}")
    assert max_additivity_sec < 1e-8, "Additivity check failed for Secondary model!"

    # 4. Table 1: Global Feature Importance Table
    print("\n4. Building Global Feature Importance Table...")
    native_imp_pri = model_pri.get_feature_importance()
    native_imp_sec = model_sec.get_feature_importance()

    importance_rows = []
    # Primary
    mean_abs_pri = np.mean(np.abs(shap_vals_pri), axis=0)
    mean_signed_pri = np.mean(shap_vals_pri, axis=0)
    std_pri = np.std(shap_vals_pri, axis=0)

    order_pri = np.argsort(mean_abs_pri)[::-1]
    for rank, idx in enumerate(order_pri, start=1):
        feat = allowlist[idx]
        importance_rows.append({
            "cohort": "CAUSAL_MATURE",
            "rank": rank,
            "feature_name": feat,
            "feature_family": get_feature_family(feat),
            "mean_abs_shap": round(float(mean_abs_pri[idx]), 4),
            "mean_signed_shap": round(float(mean_signed_pri[idx]), 4),
            "std_shap": round(float(std_pri[idx]), 4),
            "native_catboost_importance": round(float(native_imp_pri[idx]), 4),
            "availability_at_origin": "PRE_ORIGIN_OBSERVED_OR_CALENDAR_KNOWN"
        })

    # Secondary
    mean_abs_sec = np.mean(np.abs(shap_vals_sec), axis=0)
    mean_signed_sec = np.mean(shap_vals_sec, axis=0)
    std_sec = np.std(shap_vals_sec, axis=0)

    order_sec = np.argsort(mean_abs_sec)[::-1]
    for rank, idx in enumerate(order_sec, start=1):
        feat = allowlist[idx]
        importance_rows.append({
            "cohort": "LATE_MATURING",
            "rank": rank,
            "feature_name": feat,
            "feature_family": get_feature_family(feat),
            "mean_abs_shap": round(float(mean_abs_sec[idx]), 4),
            "mean_signed_shap": round(float(mean_signed_sec[idx]), 4),
            "std_shap": round(float(std_sec[idx]), 4),
            "native_catboost_importance": round(float(native_imp_sec[idx]), 4),
            "availability_at_origin": "PRE_ORIGIN_OBSERVED_OR_CALENDAR_KNOWN"
        })

    df_importance = pd.DataFrame(importance_rows)
    df_importance.to_csv(TABLES_DIR / "phase_10_shap_global_importance.csv", index=False)
    print("Saved artifacts/tables/phase_10_shap_global_importance.csv")

    # 5. Table 2: Five Canonical Local Explanation Cases
    print("\n5. Constructing Local Case Studies with Verified Additivity...")
    # Find 5 distinct rows in sample_pri:
    # 1. Typical medium demand: actual ~ 15-30
    # 2. High demand surge: actual > 100
    # 3. Intermittent zero: actual = 0, pred small
    # 4. Underforecast case: actual >> pred
    # 5. Overforecast case: pred >> actual
    sample_pri_with_idx = sample_pri.reset_index(drop=True).copy()
    sample_pri_with_idx["prediction"] = preds_pri
    sample_pri_with_idx["actual"] = sample_pri_with_idx["y_target"]
    sample_pri_with_idx["signed_err"] = sample_pri_with_idx["prediction"] - sample_pri_with_idx["actual"]

    case_indices = []
    # Case 1: Typical
    typical_idx = sample_pri_with_idx[(sample_pri_with_idx["actual"] >= 15) & (sample_pri_with_idx["actual"] <= 30)].index[0]
    case_indices.append(("LC-01", "Typical Regular Demand", typical_idx))

    # Case 2: High Surge
    surge_idx = sample_pri_with_idx[sample_pri_with_idx["actual"] > 100].sort_values("actual", ascending=False).index[0]
    case_indices.append(("LC-02", "High Demand Surge Volume", surge_idx))

    # Case 3: Intermittent Zero
    zero_idx = sample_pri_with_idx[sample_pri_with_idx["actual"] == 0].index[0]
    case_indices.append(("LC-03", "Intermittent Zero Week", zero_idx))

    # Case 4: Large Underforecast
    under_idx = sample_pri_with_idx.sort_values("signed_err", ascending=True).index[0]
    case_indices.append(("LC-04", "Severe Underforecast Distortion", under_idx))

    # Case 5: Large Overforecast
    over_idx = sample_pri_with_idx.sort_values("signed_err", ascending=False).index[0]
    case_indices.append(("LC-05", "Overforecast Ghost Demand", over_idx))

    local_rows = []
    for case_id, desc, row_i in case_indices:
        row_data = sample_pri_with_idx.iloc[row_i]
        sku = str(row_data["sku_id"])
        target_wk = str(row_data["target_week"])
        actual_val = float(row_data["actual"])
        pred_val = float(row_data["prediction"])

        # Top 5 positive and negative contributing features
        shap_row = shap_vals_pri[row_i]
        top_pos_idx = np.argsort(shap_row)[-3:][::-1]
        top_neg_idx = np.argsort(shap_row)[:3]

        top_drivers = []
        for idx in top_pos_idx:
            top_drivers.append(f"+{allowlist[idx]}={shap_row[idx]:.2f}")
        for idx in top_neg_idx:
            top_drivers.append(f"{allowlist[idx]}={shap_row[idx]:.2f}")

        local_rows.append({
            "case_id": case_id,
            "case_description": desc,
            "sku_id": sku,
            "target_week": target_wk,
            "actual_demand": actual_val,
            "model_prediction": round(pred_val, 4),
            "base_value": round(base_val_pri, 4),
            "total_shap_sum": round(float(np.sum(shap_row)), 4),
            "reconstructed_output": round(base_val_pri + float(np.sum(shap_row)), 4),
            "top_driving_features": "; ".join(top_drivers),
            "additivity_verified": True
        })

    df_local = pd.DataFrame(local_rows)
    df_local.to_csv(TABLES_DIR / "phase_10_shap_local_examples.csv", index=False)
    print("Saved artifacts/tables/phase_10_shap_local_examples.csv")

    # 6. Render Publication-Grade Figures
    print("\n6. Rendering Publication-Grade SHAP Visualizations...")

    # 6.1 Figure 1: Global SHAP Summary / Beeswarm Plot for Top 15 Features
    top15_idx = order_pri[:15]
    top15_names = [allowlist[i] for i in top15_idx]

    plt.figure(figsize=(10, 6), dpi=300)
    shap_exp = shap.Explanation(
        values=shap_vals_pri[:, top15_idx],
        base_values=np.full(len(sample_pri), base_val_pri),
        data=X_pri.iloc[:, top15_idx].values,
        feature_names=top15_names
    )
    shap.plots.beeswarm(shap_exp, max_display=15, show=False)
    plt.title("SHAP Beeswarm Summary: Top 15 Predictive Features (CatBoost MAE Primary)", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()
    fig1_path = FIGURES_DIR / "phase_10_shap_summary.png"
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"Saved {fig1_path.as_posix()}")

    # 6.2 Figure 2: Top Feature Dependence Plots
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)
    
    # Feature 1: Top feature (typically demand_lag_1 or a rolling mean)
    f1_idx = top15_idx[0]
    f1_name = allowlist[f1_idx]
    f1_x = X_pri[f1_name].values
    f1_shap = shap_vals_pri[:, f1_idx]

    axes[0].scatter(f1_x, f1_shap, alpha=0.4, color="#1f77b4", s=18)
    axes[0].set_title(f"SHAP Dependence: {f1_name}", fontsize=11, fontweight="bold")
    axes[0].set_xlabel(f"{f1_name} (Value)", fontsize=10)
    axes[0].set_ylabel("SHAP Value (Impact on Forecast)", fontsize=10)

    # Feature 2: A price or rolling aggregation feature
    f2_idx = top15_idx[1]
    f2_name = allowlist[f2_idx]
    f2_x = X_pri[f2_name].values
    f2_shap = shap_vals_pri[:, f2_idx]

    axes[1].scatter(f2_x, f2_shap, alpha=0.4, color="#ff7f0e", s=18)
    axes[1].set_title(f"SHAP Dependence: {f2_name}", fontsize=11, fontweight="bold")
    axes[1].set_xlabel(f"{f2_name} (Value)", fontsize=10)
    axes[1].set_ylabel("SHAP Value (Impact on Forecast)", fontsize=10)

    plt.suptitle("Non-Linear Feature Attributions in CatBoost Champion", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig2_path = FIGURES_DIR / "phase_10_shap_dependence_top_features.png"
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"Saved {fig2_path.as_posix()}")

    # 6.3 Figure 3: Local Attribution Waterfall for Canonical Cases
    fig, axes = plt.subplots(len(case_indices), 1, figsize=(10, 11), dpi=300)
    for plot_i, (cid, cname, row_i) in enumerate(case_indices):
        ax = axes[plot_i]
        shap_row = shap_vals_pri[row_i]
        top_k = 6
        top_k_indices = np.argsort(np.abs(shap_row))[-top_k:][::-1]
        
        feats = [allowlist[i] for i in top_k_indices]
        vals = [shap_row[i] for i in top_k_indices]
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in vals]
        
        y_pos = np.arange(len(feats))
        ax.barh(y_pos, vals, color=colors, alpha=0.85, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(feats, fontsize=8)
        ax.axvline(0, color="#666666", linewidth=0.8, linestyle="--")
        
        row_meta = sample_pri_with_idx.iloc[row_i]
        ax.set_title(
            f"[{cid}] {cname} | SKU: {row_meta['sku_id']} | Actual: {row_meta['actual']:.0f} | Pred: {row_meta['prediction']:.1f} (Base: {base_val_pri:.1f})",
            fontsize=9, fontweight="bold", pad=4
        )
        ax.tick_params(axis="x", labelsize=8)

    axes[-1].set_xlabel("SHAP Attribution (Units Impact on Prediction)", fontsize=10)
    plt.suptitle("Local Case Explanations: Feature Contributions to Individual Predictions", fontsize=12, fontweight="bold", y=0.995)
    plt.tight_layout()
    fig3_path = FIGURES_DIR / "phase_10_shap_local_cases.png"
    plt.savefig(fig3_path, dpi=300)
    plt.close()
    print(f"Saved {fig3_path.as_posix()}")

    print("\nPhase 10 SHAP Analysis Completed Successfully!")

if __name__ == "__main__":
    main()
