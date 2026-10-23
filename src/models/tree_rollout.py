"""
Tree Model Causal Recursive Rollout Engine (Phase 6.2).
Executes strictly causal multi-horizon autoregressive forecasting (H=1 to H=8)
for tree-based models (LightGBM and CatBoost) on expanding validation fold origins.

Key Governance & Causal Guarantees:
1. Zero future actual leakage: At step h >= 2, no actual realized demand is observed.
   Prior predictions y_hat_{1:h-1} (clipped at 0) are recursively pushed into the demand buffer.
2. Dynamic feature updating: Demand lags (1..26), rolling statistics (4, 8, 12, 13, 26),
   EWMA (4, 12), and demand momentum are recomputed dynamically from the prediction-generated trajectory.
3. Feature availability policies:
   - Known future calendar covariates: updated deterministically using future target week.
   - Future unobservable activity (txn count, customer count, price): ORIGIN_CARRY_FORWARD policy.
   - Deterministic counters (weeks_since_first_observed): incremented monotonically.
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

from src.models.sequence_dataset import PanelDataContainer, CALENDAR_COLUMNS


ALLOWLIST_PATH = Path("data/processed/predictor_allowlist_v1_2.json")
SPLIT_PATH = Path("data/processed/train_val_test_split_v1_1.json")


def load_allowlist() -> List[str]:
    with open(ALLOWLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [item["feature_name"] for item in data["allowed_predictors"]]


def load_split_folds() -> List[Dict[str, Any]]:
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cv_folds"]


class TreeRecursiveRolloutEngine:
    """
    Causal autoregressive rollout engine for tree models across fixed forecast origins.
    """
    def __init__(
        self,
        panel_container: Optional[PanelDataContainer] = None,
        features_parquet_path: str = "data/processed/sku_week_features_v1_2_dev.parquet"
    ):
        self.container = panel_container or PanelDataContainer()
        self.allowlist = load_allowlist()
        self.folds = load_split_folds()
        self.df_features = pd.read_parquet(features_parquet_path)

    def run_rollout_for_candidate(
        self,
        model_name: str,
        cohort: str,
        max_horizon: int = 8
    ) -> pd.DataFrame:
        """
        Executes fixed-origin recursive rollout across all 5 validation folds for a specific model candidate.
        
        Args:
            model_name: e.g. "CatBoost__MAE", "LightGBM__regression_l1"
            cohort: "CAUSAL_MATURE" or "LATE_MATURING"
            max_horizon: Horizon steps to rollout (default 8)
            
        Returns:
            DataFrame containing prediction records with actuals, clipped predictions, and horizon metadata.
        """
        records = []
        sku_idxs = self.container.get_cohort_sku_indices(cohort)
        cohort_skus = [self.container.all_skus[i] for i in sku_idxs]
        n_skus = len(cohort_skus)

        for fold_info in self.folds:
            fold_id = fold_info["fold_id"]
            origin_week = fold_info["train_target_end"]
            val_weeks = fold_info["val_target_weeks"][:max_horizon]
            origin_idx = self.container.week_to_idx[origin_week]

            # 1. Load fitted fold model
            model_file = f"{model_name}_fold{fold_id}_{cohort}.joblib"
            model_path = Path("artifacts/models/tree_models") / model_file
            if not model_path.exists():
                raise FileNotFoundError(f"Missing model artifact: {model_path}")

            bundle = joblib.load(model_path)
            model = bundle["model"] if isinstance(bundle, dict) and "model" in bundle else bundle

            # 2. Extract initial step 1 features from dev features dataset
            # (Matches exact canonical feature contract for step 1 at the forecast origin)
            step1_target_week = val_weeks[0]
            step1_df = self.df_features[
                (self.df_features["target_week"] == step1_target_week) &
                (self.df_features["cohort_tier"] == cohort)
            ].sort_values("sku_id")

            # Ensure exact SKU alignment
            step1_df = step1_df.set_index("sku_id").reindex(cohort_skus).reset_index()

            # Initialize demand history buffer up to origin: shape (n_skus, origin_idx + 1)
            # This contains all realized demand from week 0 up to origin_idx
            hist_demand = self.container.demand_mat[sku_idxs, : origin_idx + 1].copy()  # (n_skus, T_orig)

            # Initialize state tracking from step 1 feature dataframe
            current_features_df = step1_df[self.allowlist].copy()

            # State variables for recurrence
            ewma_4 = step1_df["ewma_demand_span_4"].values.copy()
            ewma_12 = step1_df["ewma_demand_span_12"].values.copy()
            alpha_4 = 2.0 / (4.0 + 1.0)
            alpha_12 = 2.0 / (12.0 + 1.0)

            weeks_since_last_sale = step1_df["weeks_since_last_sale"].values.copy()
            weeks_since_first_obs = step1_df["weeks_since_first_observed"].values.copy()
            weeks_since_last_price = step1_df["weeks_since_last_observed_price"].values.copy()

            # Carry-forward static/exogenous variables at origin
            origin_carry_forward_cols = [
                "txn_count_lag_1", "txn_count_rolling_mean_4", "unique_customer_count_lag_1",
                "price_lag_1", "price_rolling_mean_4", "last_observed_price", "has_observed_past_price"
            ]
            carry_forward_vals = {col: step1_df[col].values.copy() for col in origin_carry_forward_cols}

            # Rollout across horizons h = 1..H
            for h_step, target_week in enumerate(val_weeks, start=1):
                target_idx = self.container.week_to_idx[target_week]

                # Prediction step
                pred_raw = model.predict(current_features_df[self.allowlist])
                pred_clipped = np.maximum(0.0, pred_raw)

                # Ground truth actual
                actual_demand = self.container.demand_mat[sku_idxs, target_idx]

                # Store records for each SKU
                for i, sku in enumerate(cohort_skus):
                    records.append({
                        "model_name": model_name,
                        "cohort": cohort,
                        "fold_id": fold_id,
                        "forecast_origin": origin_week,
                        "target_week": target_week,
                        "horizon_step": h_step,
                        "sku_id": sku,
                        "prediction_raw": float(pred_raw[i]),
                        "prediction_clipped": float(pred_clipped[i]),
                        "actual": float(actual_demand[i])
                    })

                # If last horizon step, no need to update buffer for next step
                if h_step == max_horizon:
                    break

                # 3. Dynamic Autoregressive State Update for next step (h+1)
                # Append clipped prediction to demand history buffer: (n_skus, T_orig + h_step)
                hist_demand = np.concatenate([hist_demand, pred_clipped[:, None]], axis=1)

                # Update EWMA
                ewma_4 = alpha_4 * pred_clipped + (1.0 - alpha_4) * ewma_4
                ewma_12 = alpha_12 * pred_clipped + (1.0 - alpha_12) * ewma_12

                # Update activity counters
                weeks_since_last_sale = np.where(pred_clipped > 0.0, 1.0, weeks_since_last_sale + 1.0)
                weeks_since_first_obs += 1.0
                weeks_since_last_price += 1.0

                # Next target week calendar features
                next_week = val_weeks[h_step]
                next_week_idx = self.container.week_to_idx[next_week]
                next_cal = self.container.cal_mat[next_week_idx]  # (10,)

                # Construct new features dictionary for step h+1
                new_feats = {}

                # Demand lags
                for lag in [1, 2, 3, 4, 8, 12, 13, 26]:
                    new_feats[f"demand_lag_{lag}"] = hist_demand[:, -lag]

                # History sufficiency indicators
                new_feats["has_lag_1"] = np.ones(n_skus, dtype=np.float32)
                new_feats["has_lag_4"] = np.ones(n_skus, dtype=np.float32)
                new_feats["has_lag_13"] = np.ones(n_skus, dtype=np.float32)
                new_feats["has_lag_52"] = np.ones(n_skus, dtype=np.float32)

                # Rolling demand statistics
                for w in [4, 8, 12, 13, 26]:
                    win = hist_demand[:, -w:]
                    new_feats[f"rolling_mean_{w}"] = np.mean(win, axis=1)
                    new_feats[f"rolling_min_{w}"] = np.min(win, axis=1)
                    new_feats[f"rolling_max_{w}"] = np.max(win, axis=1)
                    new_feats[f"rolling_std_{w}"] = np.std(win, axis=1, ddof=1)
                    new_feats[f"rolling_zero_ratio_{w}"] = np.mean(win == 0.0, axis=1)
                    new_feats[f"rolling_positive_rate_{w}"] = np.mean(win > 0.0, axis=1)

                # EWMA
                new_feats["ewma_demand_span_4"] = ewma_4
                new_feats["ewma_demand_span_12"] = ewma_12

                # Demand momentum & differences
                d1 = new_feats["demand_lag_1"]
                d2 = new_feats["demand_lag_2"]
                d4 = new_feats["demand_lag_4"]
                new_feats["demand_diff_1_2"] = d1 - d2
                new_feats["demand_diff_1_4"] = d1 - d4
                new_feats["demand_growth_ratio_1_2"] = np.where(d2 == 0.0, 0.0, d1 / (d2 + 1.0))
                new_feats["demand_growth_ratio_1_4"] = np.where(d4 == 0.0, 0.0, d1 / (d4 + 1.0))
                new_feats["is_zero_denominator_1_2"] = (d2 == 0.0).astype(np.float32)
                new_feats["is_zero_denominator_1_4"] = (d4 == 0.0).astype(np.float32)
                new_feats["rolling_cv_8"] = new_feats["rolling_std_8"] / (new_feats["rolling_mean_8"] + 1e-4)

                # Origin carry-forward activity features
                for col in origin_carry_forward_cols:
                    new_feats[col] = carry_forward_vals[col]

                # Monotonic counters
                new_feats["weeks_since_last_sale"] = weeks_since_last_sale
                new_feats["weeks_since_first_observed"] = weeks_since_first_obs
                new_feats["weeks_since_last_observed_price"] = weeks_since_last_price

                # Deterministic calendar features for next target week
                for i_cal, cal_name in enumerate(CALENDAR_COLUMNS):
                    new_feats[cal_name] = np.full(n_skus, next_cal[i_cal], dtype=np.float32)

                # Update current_features_df for step h+1
                current_features_df = pd.DataFrame(new_feats, columns=self.allowlist)

        return pd.DataFrame(records)
