"""
Phase 9 — Error & Tail Diagnostics Engine.
Computes comprehensive post-hoc error decompositions, subgroup metrics (ABC, SBC),
zero/nonzero calibration, tail error case studies, and operational exposure proxies.

Inputs:
- artifacts/predictions/phase8_holdout_predictions.parquet
- data/processed/sku_week_demand_v1_1.csv
- artifacts/tables/eda_abc_demand.csv
- artifacts/tables/eda_sbc_primary.csv
- artifacts/tables/eda_sbc_secondary.csv

Outputs:
- artifacts/tables/phase9_error_metrics_by_model_horizon.csv
- artifacts/tables/phase9_error_metrics_by_abc_sbc.csv
- artifacts/tables/phase9_tail_cases.csv
- artifacts/tables/phase9_zero_nonzero_calibration.csv
- artifacts/tables/phase9_operational_proxies.csv
- artifacts/figures/phase9_horizon_wape_by_candidate.png
- artifacts/figures/phase9_error_distribution_by_abc.png
- artifacts/figures/phase9_sbc_regime_performance.png
- artifacts/figures/phase9_tail_error_waterfall.png
- artifacts/figures/phase9_zero_vs_nonzero_calibration.png
- project_docs/phase_09_error_tail_diagnostics.md
"""

import sys
import os
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
import seaborn as sns

from src.metrics import mae, rmse, wape, forecast_bias

# Set style for publication-grade figures
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

PREDICTIONS_PATH = PROJECT_ROOT / "artifacts/predictions/phase8_holdout_predictions.parquet"
DEMAND_PATH = PROJECT_ROOT / "data/processed/sku_week_demand_v1_1.csv"
ABC_PATH = PROJECT_ROOT / "artifacts/tables/eda_abc_demand.csv"
SBC_P_PATH = PROJECT_ROOT / "artifacts/tables/eda_sbc_primary.csv"
SBC_S_PATH = PROJECT_ROOT / "artifacts/tables/eda_sbc_secondary.csv"
TABLES_DIR = PROJECT_ROOT / "artifacts/tables"
FIGURES_DIR = PROJECT_ROOT / "artifacts/figures"
DOCS_DIR = PROJECT_ROOT / "project_docs"

os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

def main():
    print("=" * 80)
    print("PHASE 9: ERROR & TAIL DIAGNOSTICS GENERATION")
    print("=" * 80)

    # 1. Load predictions & holdout actuals
    print("1. Loading frozen holdout predictions and actuals...")
    df_preds = pd.read_parquet(PREDICTIONS_PATH)
    df_demand = pd.read_csv(DEMAND_PATH, low_memory=False, dtype={"sku_id": str})
    
    holdout_actuals = df_demand[df_demand["period_role"] == "FINAL_HOLDOUT"].copy()
    holdout_actuals["target_week"] = holdout_actuals["week_start"]
    holdout_actuals = holdout_actuals[["sku_id", "target_week", "demand", "cohort_tier"]].rename(
        columns={"demand": "actual"}
    )
    
    df_merged = pd.merge(
        df_preds,
        holdout_actuals[["sku_id", "target_week", "actual"]],
        on=["sku_id", "target_week"],
        how="inner"
    )
    assert len(df_merged) == len(df_preds), f"Mismatch in merged rows: {len(df_merged)} vs {len(df_preds)}"
    print(f"Merged dataset verified: {len(df_merged):,} records.")

    # 2. Load ABC & SBC metadata (computed strictly <= 2011-10-03)
    print("2. Loading ABC demand classes and SBC intermittency regimes...")
    df_abc = pd.read_csv(ABC_PATH, dtype={"sku_id": str})
    df_sbc_p = pd.read_csv(SBC_P_PATH, dtype={"sku_id": str})
    df_sbc_s = pd.read_csv(SBC_S_PATH, dtype={"sku_id": str})
    df_sbc = pd.concat([df_sbc_p, df_sbc_s], ignore_index=True)

    df_meta = pd.merge(
        df_abc[["sku_id", "abc_demand_class"]],
        df_sbc[["sku_id", "sbc_regime", "adi", "cv2_positive_demand"]],
        on="sku_id",
        how="inner"
    )
    
    df_full = pd.merge(df_merged, df_meta, on="sku_id", how="left")
    print(f"Enriched dataset shape: {df_full.shape}")

    # Add error columns
    df_full["abs_error"] = np.abs(df_full["actual"] - df_full["prediction"])
    df_full["signed_error"] = df_full["prediction"] - df_full["actual"] # positive = overforecast, negative = underforecast
    df_full["sq_error"] = (df_full["actual"] - df_full["prediction"]) ** 2

    # 3. Table 1: Error metrics by model and horizon step (h=1..8, cum H=4, cum H=8)
    print("3. Computing Error Metrics by Model, Cohort, and Horizon...")
    horizon_rows = []
    
    for (model, cohort), grp in df_full.groupby(["model_id", "cohort"]):
        # Individual steps h=1..8
        for h in range(1, 9):
            sub = grp[grp["horizon_step"] == h]
            y_t = sub["actual"].values
            y_p = sub["prediction"].values
            horizon_rows.append({
                "model_id": model,
                "cohort": cohort,
                "horizon_scope": f"Step_h{h}",
                "horizon_step": h,
                "n_records": len(sub),
                "actual_volume": float(np.sum(y_t)),
                "pred_volume": float(np.sum(y_p)),
                "wape_pct": round(float(wape(y_t, y_p) * 100.0), 2),
                "mae": round(float(mae(y_t, y_p)), 4),
                "rmse": round(float(rmse(y_t, y_p)), 4),
                "signed_bias_pct": round(float(forecast_bias(y_t, y_p) * 100.0), 2)
            })
        
        # Cumulative H=4
        sub_h4 = grp[grp["horizon_step"] <= 4]
        y_t4 = sub_h4["actual"].values
        y_p4 = sub_h4["prediction"].values
        horizon_rows.append({
            "model_id": model,
            "cohort": cohort,
            "horizon_scope": "Cumulative_H4",
            "horizon_step": 4,
            "n_records": len(sub_h4),
            "actual_volume": float(np.sum(y_t4)),
            "pred_volume": float(np.sum(y_p4)),
            "wape_pct": round(float(wape(y_t4, y_p4) * 100.0), 2),
            "mae": round(float(mae(y_t4, y_p4)), 4),
            "rmse": round(float(rmse(y_t4, y_p4)), 4),
            "signed_bias_pct": round(float(forecast_bias(y_t4, y_p4) * 100.0), 2)
        })

        # Cumulative H=8
        sub_h8 = grp[grp["horizon_step"] <= 8]
        y_t8 = sub_h8["actual"].values
        y_p8 = sub_h8["prediction"].values
        horizon_rows.append({
            "model_id": model,
            "cohort": cohort,
            "horizon_scope": "Cumulative_H8",
            "horizon_step": 8,
            "n_records": len(sub_h8),
            "actual_volume": float(np.sum(y_t8)),
            "pred_volume": float(np.sum(y_p8)),
            "wape_pct": round(float(wape(y_t8, y_p8) * 100.0), 2),
            "mae": round(float(mae(y_t8, y_p8)), 4),
            "rmse": round(float(rmse(y_t8, y_p8)), 4),
            "signed_bias_pct": round(float(forecast_bias(y_t8, y_p8) * 100.0), 2)
        })

    df_horizon_metrics = pd.DataFrame(horizon_rows)
    df_horizon_metrics.to_csv(TABLES_DIR / "phase9_error_metrics_by_model_horizon.csv", index=False)
    print("Saved artifacts/tables/phase9_error_metrics_by_model_horizon.csv")

    # 4. Table 2: Error metrics by ABC Class and SBC Intermittency Regime
    print("4. Computing Subgroup Error Metrics (ABC and SBC)...")
    abc_sbc_rows = []
    
    # We evaluate at cumulative H=4 (the operational inventory review horizon) and cumulative H=8
    for (model, cohort), grp in df_full.groupby(["model_id", "cohort"]):
        for horizon_scope, max_h in [("Cumulative_H4", 4), ("Cumulative_H8", 8)]:
            sub_h = grp[grp["horizon_step"] <= max_h]
            
            # ABC breakdown
            for abc_cls in ["A", "B", "C"]:
                sub_abc = sub_h[sub_h["abc_demand_class"] == abc_cls]
                if len(sub_abc) > 0:
                    y_t = sub_abc["actual"].values
                    y_p = sub_abc["prediction"].values
                    # Macro WAPE per SKU
                    sku_wapes = []
                    for _, sku_grp in sub_abc.groupby("sku_id"):
                        sy = sku_grp["actual"].values
                        sp = sku_grp["prediction"].values
                        if np.sum(sy) > 0:
                            sku_wapes.append(float(np.sum(np.abs(sy - sp)) / np.sum(sy)))
                    macro_wape_pct = round(float(np.mean(sku_wapes) * 100.0), 2) if sku_wapes else np.nan

                    abc_sbc_rows.append({
                        "model_id": model,
                        "cohort": cohort,
                        "horizon_scope": horizon_scope,
                        "segment_type": "ABC_DEMAND",
                        "segment_value": abc_cls,
                        "sku_count": sub_abc["sku_id"].nunique(),
                        "n_records": len(sub_abc),
                        "actual_volume": float(np.sum(y_t)),
                        "pred_volume": float(np.sum(y_p)),
                        "pooled_wape_pct": round(float(wape(y_t, y_p) * 100.0), 2),
                        "macro_wape_pct": macro_wape_pct,
                        "mae": round(float(mae(y_t, y_p)), 4),
                        "rmse": round(float(rmse(y_t, y_p)), 4),
                        "signed_bias_pct": round(float(forecast_bias(y_t, y_p) * 100.0), 2)
                    })

            # SBC regime breakdown
            for sbc_reg in ["Smooth", "Erratic", "Lumpy", "Intermittent"]:
                sub_sbc = sub_h[sub_h["sbc_regime"] == sbc_reg]
                if len(sub_sbc) > 0:
                    y_t = sub_sbc["actual"].values
                    y_p = sub_sbc["prediction"].values
                    sku_wapes = []
                    for _, sku_grp in sub_sbc.groupby("sku_id"):
                        sy = sku_grp["actual"].values
                        sp = sku_grp["prediction"].values
                        if np.sum(sy) > 0:
                            sku_wapes.append(float(np.sum(np.abs(sy - sp)) / np.sum(sy)))
                    macro_wape_pct = round(float(np.mean(sku_wapes) * 100.0), 2) if sku_wapes else np.nan

                    abc_sbc_rows.append({
                        "model_id": model,
                        "cohort": cohort,
                        "horizon_scope": horizon_scope,
                        "segment_type": "SBC_INTERMITTENCY",
                        "segment_value": sbc_reg,
                        "sku_count": sub_sbc["sku_id"].nunique(),
                        "n_records": len(sub_sbc),
                        "actual_volume": float(np.sum(y_t)),
                        "pred_volume": float(np.sum(y_p)),
                        "pooled_wape_pct": round(float(wape(y_t, y_p) * 100.0), 2),
                        "macro_wape_pct": macro_wape_pct,
                        "mae": round(float(mae(y_t, y_p)), 4),
                        "rmse": round(float(rmse(y_t, y_p)), 4),
                        "signed_bias_pct": round(float(forecast_bias(y_t, y_p) * 100.0), 2)
                    })

    df_abc_sbc = pd.DataFrame(abc_sbc_rows)
    df_abc_sbc.to_csv(TABLES_DIR / "phase9_error_metrics_by_abc_sbc.csv", index=False)
    print("Saved artifacts/tables/phase9_error_metrics_by_abc_sbc.csv")

    # 5. Table 3: Zero vs Non-Zero Demand Calibration
    print("5. Analyzing Zero vs Non-Zero Demand Calibration...")
    zero_rows = []
    for (model, cohort), grp in df_full.groupby(["model_id", "cohort"]):
        # H=4 slice
        sub = grp[grp["horizon_step"] <= 4]
        
        # Zero actuals subset
        zero_act = sub[sub["actual"] == 0]
        n_zero_act = len(zero_act)
        false_positive_count = int(np.sum(zero_act["prediction"] > 0))
        false_positive_vol = float(np.sum(zero_act["prediction"]))
        zero_pred_given_zero_act = float(np.mean(zero_act["prediction"] == 0)) if n_zero_act > 0 else 0.0
        
        # Non-zero actuals subset
        nonzero_act = sub[sub["actual"] > 0]
        n_nonzero_act = len(nonzero_act)
        missed_demand_count = int(np.sum(nonzero_act["prediction"] == 0))
        missed_demand_vol = float(np.sum(nonzero_act[nonzero_act["prediction"] == 0]["actual"]))
        under_count = int(np.sum(nonzero_act["prediction"] < nonzero_act["actual"]))
        over_count = int(np.sum(nonzero_act["prediction"] > nonzero_act["actual"]))
        exact_count = int(np.sum(nonzero_act["prediction"] == nonzero_act["actual"]))

        zero_rows.append({
            "model_id": model,
            "cohort": cohort,
            "horizon_scope": "Cumulative_H4",
            "total_records": len(sub),
            "zero_actual_records": n_zero_act,
            "zero_actual_share_pct": round(n_zero_act / len(sub) * 100.0, 2),
            "false_positive_forecast_count": false_positive_count,
            "false_positive_forecast_rate_pct": round(false_positive_count / n_zero_act * 100.0, 2) if n_zero_act > 0 else 0.0,
            "false_positive_volume": round(false_positive_vol, 1),
            "zero_forecast_accuracy_pct": round(zero_pred_given_zero_act * 100.0, 2),
            "nonzero_actual_records": n_nonzero_act,
            "nonzero_actual_volume": float(np.sum(nonzero_act["actual"])),
            "missed_demand_count": missed_demand_count,
            "missed_demand_rate_pct": round(missed_demand_count / n_nonzero_act * 100.0, 2) if n_nonzero_act > 0 else 0.0,
            "missed_demand_volume": round(missed_demand_vol, 1),
            "underforecast_count": under_count,
            "underforecast_rate_pct": round(under_count / n_nonzero_act * 100.0, 2) if n_nonzero_act > 0 else 0.0,
            "overforecast_count": over_count,
            "overforecast_rate_pct": round(over_count / n_nonzero_act * 100.0, 2) if n_nonzero_act > 0 else 0.0
        })

    df_zero_nonzero = pd.DataFrame(zero_rows)
    df_zero_nonzero.to_csv(TABLES_DIR / "phase9_zero_nonzero_calibration.csv", index=False)
    print("Saved artifacts/tables/phase9_zero_nonzero_calibration.csv")

    # 6. Table 4: Tail Errors and Case Studies
    print("6. Extracting Extreme Tail Cases and In-Depth Case Studies...")
    cat_df = df_full[(df_full["model_id"] == "CatBoost__MAE") & (df_full["cohort"] == "CAUSAL_MATURE")].copy()
    
    # 6.1 Top absolute errors
    top_abs = cat_df.sort_values("abs_error", ascending=False).head(20).copy()
    top_abs["case_type"] = "TOP_ABSOLUTE_ERROR"

    # 6.2 Top relative errors for stable positive demand (actual >= 10)
    stable_pos = cat_df[cat_df["actual"] >= 10].copy()
    stable_pos["rel_error"] = stable_pos["abs_error"] / stable_pos["actual"]
    top_rel = stable_pos.sort_values("rel_error", ascending=False).head(20).copy()
    top_rel["case_type"] = "TOP_RELATIVE_ERROR_STABLE_DEMAND"

    # 6.3 Top overforecast errors (prediction >> actual)
    top_over = cat_df.sort_values("signed_error", ascending=False).head(20).copy()
    top_over["case_type"] = "TOP_OVERFORECAST"

    # 6.4 Top underforecast errors (actual >> prediction)
    top_under = cat_df.sort_values("signed_error", ascending=True).head(20).copy()
    top_under["case_type"] = "TOP_UNDERFORECAST"

    df_tail_all = pd.concat([top_abs, top_rel, top_over, top_under], ignore_index=True)
    df_tail_all.to_csv(TABLES_DIR / "phase9_tail_cases.csv", index=False)
    print("Saved artifacts/tables/phase9_tail_cases.csv")

    # Select 5 specific in-depth case studies representing distinct failure modes
    print("\n--- Selecting 5 Distinct Canonical Case Studies ---")
    case_1 = top_under.iloc[0] # Worst absolute underforecast (surge spike)
    case_2 = top_rel.iloc[0]   # Worst percentage error on stable demand
    
    # Case 3: Intermittent / Lumpy SKU with actual positive spike after zeros
    lumpy_cases = cat_df[(cat_df["sbc_regime"] == "Lumpy") & (cat_df["actual"] >= 50)].sort_values("abs_error", ascending=False)
    case_3 = lumpy_cases.iloc[0]
    
    # Case 4: Zero demand overforecast (actual = 0, but prediction > 10)
    zero_over_cases = cat_df[cat_df["actual"] == 0].sort_values("prediction", ascending=False)
    case_4 = zero_over_cases.iloc[0]

    # Case 5: Large bulk order demand spike (wholesale transaction spike >= 500)
    bulk_spike = cat_df[cat_df["actual"] >= 500].sort_values("actual", ascending=False)
    case_5 = bulk_spike.iloc[0]

    case_studies = [
        {"case_id": "CS-01", "name": "Severe Demand Surge / Absolute Underforecast", "data": case_1},
        {"case_id": "CS-02", "name": "Relative Distortion on Stable Demand", "data": case_2},
        {"case_id": "CS-03", "name": "Lumpy Intermittent Spike Miss", "data": case_3},
        {"case_id": "CS-04", "name": "Zero-Demand Ghost Overforecast", "data": case_4},
        {"case_id": "CS-05", "name": "Wholesale Bulk Order Demand Spike", "data": case_5}
    ]

    for cs in case_studies:
        d = cs["data"]
        print(f"[{cs['case_id']}] {cs['name']}: SKU={d['sku_id']}, Week={d['target_week']}, Actual={d['actual']}, Pred={round(d['prediction'], 2)}, AbsErr={round(d['abs_error'], 2)}, ABC={d['abc_demand_class']}, SBC={d['sbc_regime']}")

    # 7. Table 5: Operational Exposure Proxies
    print("\n7. Computing Operational Exposure Proxies (Stockout & Overstock Risks)...")
    op_rows = []
    for (model, cohort), grp in df_full.groupby(["model_id", "cohort"]):
        sub_h4 = grp[grp["horizon_step"] <= 4]
        
        # Proxy metrics
        # Stockout risk proxy: sum of max(0, actual - pred)
        unmet_demand_proxy = np.maximum(0.0, sub_h4["actual"].values - sub_h4["prediction"].values)
        total_unmet = float(np.sum(unmet_demand_proxy))
        
        # Excess inventory holding proxy: sum of max(0, pred - actual)
        excess_holding_proxy = np.maximum(0.0, sub_h4["prediction"].values - sub_h4["actual"].values)
        total_excess = float(np.sum(excess_holding_proxy))

        total_actual = float(np.sum(sub_h4["actual"]))
        total_pred = float(np.sum(sub_h4["prediction"]))

        op_rows.append({
            "model_id": model,
            "cohort": cohort,
            "horizon_scope": "Cumulative_H4",
            "total_actual_volume": total_actual,
            "total_pred_volume": total_pred,
            "unmet_demand_proxy_units": round(total_unmet, 1),
            "unmet_demand_share_actual_pct": round(total_unmet / total_actual * 100.0, 2) if total_actual > 0 else 0.0,
            "excess_holding_proxy_units": round(total_excess, 1),
            "excess_holding_share_pred_pct": round(total_excess / total_pred * 100.0, 2) if total_pred > 0 else 0.0,
            "service_proxy_fill_rate_pct": round(100.0 - (total_unmet / total_actual * 100.0), 2) if total_actual > 0 else 0.0
        })

    df_op = pd.DataFrame(op_rows)
    df_op.to_csv(TABLES_DIR / "phase9_operational_proxies.csv", index=False)
    print("Saved artifacts/tables/phase9_operational_proxies.csv")

    # 8. Render Publication-Grade Visualizations
    print("\n8. Generating Publication-Grade Visualizations...")
    
    # 8.1 Figure 1: Horizon WAPE Degradation by Candidate (Primary Cohort)
    plt.figure(figsize=(9, 5), dpi=300)
    pri_horizon = df_horizon_metrics[(df_horizon_metrics["cohort"] == "CAUSAL_MATURE") & (df_horizon_metrics["horizon_scope"].str.startswith("Step_h"))]
    
    palette = {
        "CatBoost__MAE": "#1f77b4",
        "TiDE_Sequence_v1": "#2ca02c",
        "CatBoost__Tweedie_p15": "#ff7f0e",
        "MA_4": "#7f7f7f",
        "Naive_1": "#d62728"
    }
    
    for model_id, m_grp in pri_horizon.groupby("model_id"):
        plt.plot(
            m_grp["horizon_step"],
            m_grp["wape_pct"],
            marker="o",
            linewidth=2.0,
            label=model_id,
            color=palette.get(model_id, "#333333")
        )
    
    plt.title("Holdout Horizon Degradation: Per-Step WAPE (h=1..8) — Primary Cohort", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Forecast Horizon Step (Weeks Ahead, h)", fontsize=11)
    plt.ylabel("Pooled WAPE (%)", fontsize=11)
    plt.xticks(range(1, 9))
    plt.ylim(55, 115)
    plt.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=10)
    plt.tight_layout()
    fig1_path = FIGURES_DIR / "phase9_horizon_wape_by_candidate.png"
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"Saved {fig1_path.as_posix()}")

    # 8.2 Figure 2: Error Distribution by ABC Demand Class (Cumulative H=4)
    plt.figure(figsize=(10, 5), dpi=300)
    pri_abc = df_abc_sbc[(df_abc_sbc["cohort"] == "CAUSAL_MATURE") & (df_abc_sbc["segment_type"] == "ABC_DEMAND") & (df_abc_sbc["horizon_scope"] == "Cumulative_H4")]
    
    # Bar chart comparing CatBoost MAE, Tweedie, TiDE, and MA_4
    sub_models = ["CatBoost__MAE", "CatBoost__Tweedie_p15", "TiDE_Sequence_v1", "MA_4"]
    plot_df = pri_abc[pri_abc["model_id"].isin(sub_models)]
    
    sns.barplot(
        data=plot_df,
        x="segment_value",
        y="pooled_wape_pct",
        hue="model_id",
        palette=[palette[m] for m in sub_models],
        order=["A", "B", "C"]
    )
    plt.title("Error by Demand Volume: Cumulative H=4 WAPE across ABC Classes", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("ABC Demand Class (Pareto Volume Tier)", fontsize=11)
    plt.ylabel("Pooled WAPE (%)", fontsize=11)
    plt.legend(title="Candidate", frameon=True, facecolor="white", edgecolor="#cccccc")
    plt.tight_layout()
    fig2_path = FIGURES_DIR / "phase9_error_distribution_by_abc.png"
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"Saved {fig2_path.as_posix()}")

    # 8.3 Figure 3: SBC Intermittency Regime Performance (Cumulative H=4)
    plt.figure(figsize=(10, 5), dpi=300)
    pri_sbc = df_abc_sbc[(df_abc_sbc["cohort"] == "CAUSAL_MATURE") & (df_abc_sbc["segment_type"] == "SBC_INTERMITTENCY") & (df_abc_sbc["horizon_scope"] == "Cumulative_H4")]
    plot_sbc = pri_sbc[pri_sbc["model_id"].isin(sub_models)]

    sns.barplot(
        data=plot_sbc,
        x="segment_value",
        y="pooled_wape_pct",
        hue="model_id",
        palette=[palette[m] for m in sub_models],
        order=["Smooth", "Erratic", "Lumpy", "Intermittent"]
    )
    plt.title("Syntetos-Boylan-Croston (SBC) Regime Diagnostic: Cumulative H=4 WAPE", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("SBC Intermittency Regime", fontsize=11)
    plt.ylabel("Pooled WAPE (%)", fontsize=11)
    plt.legend(title="Candidate", frameon=True, facecolor="white", edgecolor="#cccccc")
    plt.tight_layout()
    fig3_path = FIGURES_DIR / "phase9_sbc_regime_performance.png"
    plt.savefig(fig3_path, dpi=300)
    plt.close()
    print(f"Saved {fig3_path.as_posix()}")

    # 8.4 Figure 4: Tail Error Waterfall (Top 15 Absolute Errors for CatBoost MAE)
    plt.figure(figsize=(11, 5.5), dpi=300)
    top15 = top_abs.head(15).copy()
    top15["sku_label"] = top15["sku_id"].astype(str) + " (" + top15["target_week"].str[-5:] + ")"
    
    x = np.arange(len(top15))
    width = 0.38
    plt.bar(x - width/2, top15["actual"], width=width, label="Actual Demand", color="#1f77b4", alpha=0.9)
    plt.bar(x + width/2, top15["prediction"], width=width, label="Forecast (CatBoost MAE)", color="#ff7f0e", alpha=0.9)
    
    plt.title("Top 15 Absolute Error Tail Events: Realized Surges vs Point Forecasts", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("SKU ID (Target Week MM-DD)", fontsize=11)
    plt.ylabel("Weekly Units", fontsize=11)
    plt.xticks(x, top15["sku_label"], rotation=45, ha="right", fontsize=9)
    plt.legend(frameon=True, facecolor="white", edgecolor="#cccccc")
    plt.tight_layout()
    fig4_path = FIGURES_DIR / "phase9_tail_error_waterfall.png"
    plt.savefig(fig4_path, dpi=300)
    plt.close()
    print(f"Saved {fig4_path.as_posix()}")

    # 8.5 Figure 5: Zero vs Non-Zero Demand Calibration
    plt.figure(figsize=(9, 5), dpi=300)
    pri_zero = df_zero_nonzero[df_zero_nonzero["cohort"] == "CAUSAL_MATURE"].copy()
    plot_znz = pri_zero[pri_zero["model_id"].isin(sub_models)]

    x = np.arange(len(plot_znz))
    width = 0.35
    plt.bar(x - width/2, plot_znz["false_positive_forecast_rate_pct"], width=width, label="False-Positive Rate on Zero Actuals (%)", color="#e377c2")
    plt.bar(x + width/2, plot_znz["missed_demand_rate_pct"], width=width, label="Missed Demand Rate on Non-Zero Actuals (%)", color="#17becf")

    plt.title("Zero/Non-Zero Demand Calibration: False Positives vs Missed Demand", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Model Candidate", fontsize=11)
    plt.ylabel("Rate (%)", fontsize=11)
    plt.xticks(x, plot_znz["model_id"], fontsize=10)
    plt.legend(frameon=True, facecolor="white", edgecolor="#cccccc")
    plt.tight_layout()
    fig5_path = FIGURES_DIR / "phase9_zero_vs_nonzero_calibration.png"
    plt.savefig(fig5_path, dpi=300)
    plt.close()
    print(f"Saved {fig5_path.as_posix()}")

    print("\nPhase 9 Diagnostics Completed Successfully!")

if __name__ == "__main__":
    main()
