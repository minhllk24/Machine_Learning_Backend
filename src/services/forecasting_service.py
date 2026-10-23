"""
Forecasting Service interface and domain boundary.
Validates business rules, model serving readiness, coordinates inference execution,
and persists runs atomically to SQLite storage.
Strictly prohibits generating mock or fake forecast numbers when models are NOT_READY.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import uuid
import numpy as np
import pandas as pd
import torch

from src.core.config import settings
from src.core.logging_config import logger
from src.api.errors import (
    AppException,
    ModelNotFoundException,
    ModelNotReadyException,
    UnsupportedHorizonException,
    SKUNotFoundException,
    ErrorCode,
)
from src.api.schemas.forecast import (
    ForecastRequest,
    ForecastResponse,
    SKUForecastRecord,
)
from src.api.schemas.models import ServingStatus
from src.services.model_registry import ModelRegistryService, registry_service
from src.services.persistence_service import PersistenceService, persistence_service
from src.models.sequence_dataset import PanelDataContainer, CALENDAR_COLUMNS
from src.models.tide_sequence import TiDESequenceModel
from src.features import build_features_v1_2


class ForecastingService:
    """Service boundary governing forecast invocation, multi-week inference, and persistence."""

    def __init__(
        self,
        registry: Optional[ModelRegistryService] = None,
        persistence: Optional[PersistenceService] = None
    ):
        self.registry = registry or registry_service
        self.persistence = persistence or persistence_service
        self._panel: Optional[PanelDataContainer] = None
        self._step1_features_df: Optional[pd.DataFrame] = None
        self._fut_cal_mat: Optional[np.ndarray] = None
        self._allowlist: Optional[List[str]] = None

    def _get_allowlist(self) -> List[str]:
        if self._allowlist is None:
            with open(settings.ALLOWLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._allowlist = [item["feature_name"] for item in data["allowed_predictors"]]
        return self._allowlist

    def _get_panel(self) -> PanelDataContainer:
        if self._panel is None:
            logger.info("Initializing in-memory PanelDataContainer for forecasting service...")
            self._panel = PanelDataContainer()
        return self._panel

    def _get_step1_features_and_calendar(self) -> Tuple[pd.DataFrame, np.ndarray]:
        if self._step1_features_df is None or self._fut_cal_mat is None:
            logger.info("Building initial step 1 features and calendar matrix for origin 2011-10-03...")
            demand_path = settings.DATA_DIR / "processed" / "sku_week_demand_v1_1.csv"
            df_demand = pd.read_csv(demand_path, low_memory=False, dtype={"sku_id": str})
            
            # Mask holdout period to ensure zero leakage
            mask_holdout = df_demand["week_start"] >= "2011-10-10"
            df_demand.loc[mask_holdout, "demand"] = 0.0
            df_demand.loc[mask_holdout, "avg_unit_price"] = 0.0
            df_demand.loc[mask_holdout, "transaction_count"] = 0.0
            df_demand.loc[mask_holdout, "unique_customer_count"] = 0.0

            cross_path = settings.TABLES_DIR / "eda_abc_xyz_cross.csv"
            sbc_p_path = settings.TABLES_DIR / "eda_sbc_primary.csv"
            sbc_s_path = settings.TABLES_DIR / "eda_sbc_secondary.csv"
            cross_df = pd.read_csv(cross_path, dtype={"sku_id": str}) if cross_path.exists() else None
            sbc_p = pd.read_csv(sbc_p_path, dtype={"sku_id": str}) if sbc_p_path.exists() else None
            sbc_s = pd.read_csv(sbc_s_path, dtype={"sku_id": str}) if sbc_s_path.exists() else None

            feats = build_features_v1_2(df_demand, cross_df, sbc_p, sbc_s)
            self._step1_features_df = feats[feats["target_week"] == "2011-10-10"].copy()

            target_weeks = [
                "2011-10-10", "2011-10-17", "2011-10-24", "2011-10-31",
                "2011-11-07", "2011-11-14", "2011-11-21", "2011-11-28"
            ]
            cal_df = feats[feats["target_week"].isin(target_weeks)][["target_week"] + CALENDAR_COLUMNS].drop_duplicates().sort_values("target_week")
            self._fut_cal_mat = cal_df[CALENDAR_COLUMNS].values.astype(np.float32)

        return self._step1_features_df, self._fut_cal_mat

    def generate_forecast(self, request: ForecastRequest, user_id: Optional[str] = None) -> ForecastResponse:
        """
        Coordinates forecast calculation for the requested SKUs and horizon.
        Executes real production candidate inference when models are SERVING_READY.
        Persists runs and prediction records atomically.
        """
        logger.info(
            f"Forecast requested: model='{request.model_id}', origin='{request.forecast_origin}', "
            f"horizon={request.horizon_weeks}, skus_count={len(request.sku_ids)}, user_id='{user_id}'"
        )

        # 1. Lookup model in registry
        model_detail = self.registry.get_model(request.model_id)

        # 2. Check serving readiness
        if model_detail.serving_status != ServingStatus.SERVING_READY:
            logger.warning(
                f"Model '{request.model_id}' rejected for inference: status is {model_detail.serving_status}"
            )
            raise ModelNotReadyException(
                model_id=request.model_id,
                readiness_reasons=model_detail.readiness_reasons
            )

        # 3. Horizon verification
        max_allowed_h = min(max(model_detail.supported_horizons, default=4), 4)
        if request.horizon_weeks not in model_detail.supported_horizons or request.horizon_weeks > 4:
            raise UnsupportedHorizonException(
                horizon_weeks=request.horizon_weeks,
                max_allowed=max_allowed_h
            )

        # 4. SKU Validation
        panel = self._get_panel()
        unknown_skus = [sku for sku in request.sku_ids if sku not in panel.sku_to_idx]
        if unknown_skus:
            raise SKUNotFoundException(unknown_skus[0])

        # 5. Forecast Origin Validation
        # Validated production models are trained through 2011-10-03
        if request.forecast_origin > "2011-10-03":
            raise AppException(
                status_code=422,
                error_code=ErrorCode.VALIDATION_ERROR,
                message=f"Forecast origin '{request.forecast_origin}' exceeds historical development pool cutoff ('2011-10-03').",
                details={"max_allowed_origin": "2011-10-03", "requested_origin": request.forecast_origin}
            )

        # 6. Initialize Run in Persistence
        forecast_run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.persistence.create_run(
            forecast_run_id=forecast_run_id,
            model_id=request.model_id,
            model_version=model_detail.model_version,
            forecast_origin=request.forecast_origin,
            horizon_weeks=request.horizon_weeks,
            requested_sku_count=len(request.sku_ids),
            training_cutoff=model_detail.training_cutoff,
            forecast_strategy=model_detail.algorithm_family,
            request_metadata={
                "requested_sku_ids": request.sku_ids,
                "model_name": model_detail.model_name
            },
            user_id=user_id,
        )

        try:
            records = self._execute_inference(
                model_name=model_detail.model_name,
                requested_skus=request.sku_ids,
                horizon_weeks=request.horizon_weeks,
                forecast_origin=request.forecast_origin
            )

            # 7. Persist records atomically
            self.persistence.persist_run_predictions(
                forecast_run_id=forecast_run_id,
                records=records
            )

            # 8. Build response
            prediction_items = [
                SKUForecastRecord(
                    sku_id=r["sku_id"],
                    target_week=r["target_week"],
                    horizon_step=r["horizon_step"],
                    prediction=r["prediction"],
                    prediction_status=r["prediction_status"]
                )
                for r in records
            ]

            return ForecastResponse(
                forecast_run_id=forecast_run_id,
                model_id=request.model_id,
                model_version=model_detail.model_version,
                forecast_origin=request.forecast_origin,
                horizon_weeks=request.horizon_weeks,
                data_snapshot_id="v1.2-dev",
                predictions=prediction_items,
                warnings=[]
            )

        except Exception as exc:
            logger.error(f"Inference execution failed for run '{forecast_run_id}': {exc}", exc_info=True)
            self.persistence.record_run_failure(
                forecast_run_id=forecast_run_id,
                failure_code="INFERENCE_EXECUTION_ERROR",
                failure_message=str(exc)
            )
            raise AppException(
                status_code=500,
                error_code=ErrorCode.INTERNAL_PROCESSING_ERROR,
                message=f"Inference execution failed: {str(exc)}",
                details={"forecast_run_id": forecast_run_id}
            )

    def _execute_inference(
        self,
        model_name: str,
        requested_skus: List[str],
        horizon_weeks: int,
        forecast_origin: str
    ) -> List[Dict[str, Any]]:
        """Executes actual multi-week inference pipeline for the requested model and SKUs."""
        panel = self._get_panel()
        allowlist = self._get_allowlist()
        step1_features_df, fut_cal_mat = self._get_step1_features_and_calendar()

        # Compute target week dates
        origin_dt = pd.to_datetime(forecast_origin)
        target_weeks = [
            (origin_dt + pd.Timedelta(days=7 * h)).strftime("%Y-%m-%d")
            for h in range(1, horizon_weeks + 1)
        ]

        # Partition SKUs by cohort tier
        sku_to_cohort = panel.sku_cohort_map
        cohort_groups: Dict[str, List[str]] = {}
        for sku in requested_skus:
            c = sku_to_cohort.get(sku, "CAUSAL_MATURE")
            cohort_groups.setdefault(c, []).append(sku)

        all_records = []

        is_catboost = "catboost" in model_name.lower()
        is_tide = "tide" in model_name.lower()

        for cohort, cohort_skus in cohort_groups.items():
            sku_indices = [panel.sku_to_idx[sku] for sku in cohort_skus]
            n_skus = len(cohort_skus)

            if is_catboost:
                # Load CatBoost model for this cohort
                model_artifact_id = f"{model_name}_{cohort}"
                cb_model = self.registry.load_model_artifact(model_artifact_id)

                # Step 1 feature subset
                step1_cohort = step1_features_df[step1_features_df["cohort_tier"] == cohort].copy()
                step1_cohort = step1_cohort.set_index("sku_id").reindex(cohort_skus).reset_index()

                # Demand buffer up to origin (96 weeks)
                hist_demand = panel.demand_mat[sku_indices, : 96].copy()

                current_features_df = step1_cohort[allowlist].copy()
                ewma_4 = step1_cohort["ewma_demand_span_4"].values.copy()
                ewma_12 = step1_cohort["ewma_demand_span_12"].values.copy()
                alpha_4 = 2.0 / 5.0
                alpha_12 = 2.0 / 13.0

                weeks_since_last_sale = step1_cohort["weeks_since_last_sale"].values.copy()
                weeks_since_first_obs = step1_cohort["weeks_since_first_observed"].values.copy()
                weeks_since_last_price = step1_cohort["weeks_since_last_observed_price"].values.copy()

                origin_carry_cols = [
                    "txn_count_lag_1", "txn_count_rolling_mean_4", "unique_customer_count_lag_1",
                    "price_lag_1", "price_rolling_mean_4", "last_observed_price", "has_observed_past_price"
                ]
                carry_vals = {col: step1_cohort[col].values.copy() for col in origin_carry_cols}

                for h_step, target_week in enumerate(target_weeks, start=1):
                    pred_raw = cb_model.predict(current_features_df[allowlist])
                    pred_clipped = np.maximum(0.0, pred_raw)

                    for i, sku in enumerate(cohort_skus):
                        r_val = float(pred_raw[i])
                        c_val = float(pred_clipped[i])
                        all_records.append({
                            "sku_id": sku,
                            "target_week": target_week,
                            "horizon_step": h_step,
                            "prediction": c_val,
                            "prediction_raw": r_val,
                            "prediction_status": "INFERRED",
                            "clipped_at_zero": 1 if r_val < 0.0 else 0
                        })

                    if h_step == horizon_weeks:
                        break

                    # Autoregressive update for h+1
                    hist_demand = np.concatenate([hist_demand, pred_clipped[:, None]], axis=1)
                    ewma_4 = alpha_4 * pred_clipped + (1.0 - alpha_4) * ewma_4
                    ewma_12 = alpha_12 * pred_clipped + (1.0 - alpha_12) * ewma_12
                    weeks_since_last_sale = np.where(pred_clipped > 0.0, 1.0, weeks_since_last_sale + 1.0)
                    weeks_since_first_obs += 1.0
                    weeks_since_last_price += 1.0

                    next_cal = fut_cal_mat[h_step]

                    new_feats = {}
                    for lag in [1, 2, 3, 4, 8, 12, 13, 26]:
                        new_feats[f"demand_lag_{lag}"] = hist_demand[:, -lag]
                    new_feats["has_lag_1"] = np.ones(n_skus, dtype=np.float32)
                    new_feats["has_lag_4"] = np.ones(n_skus, dtype=np.float32)
                    new_feats["has_lag_13"] = np.ones(n_skus, dtype=np.float32)
                    new_feats["has_lag_52"] = np.ones(n_skus, dtype=np.float32)

                    for w in [4, 8, 12, 13, 26]:
                        win = hist_demand[:, -w:]
                        new_feats[f"rolling_mean_{w}"] = np.mean(win, axis=1)
                        new_feats[f"rolling_min_{w}"] = np.min(win, axis=1)
                        new_feats[f"rolling_max_{w}"] = np.max(win, axis=1)
                        new_feats[f"rolling_std_{w}"] = np.std(win, axis=1, ddof=1)
                        new_feats[f"rolling_zero_ratio_{w}"] = np.mean(win == 0.0, axis=1)
                        new_feats[f"rolling_positive_rate_{w}"] = np.mean(win > 0.0, axis=1)

                    new_feats["ewma_demand_span_4"] = ewma_4
                    new_feats["ewma_demand_span_12"] = ewma_12

                    d1 = new_feats["demand_lag_1"]
                    d2 = new_feats["demand_lag_2"]
                    d4 = new_feats["demand_lag_4"]
                    new_feats["demand_diff_1_2"] = d1 - d2
                    new_feats["demand_diff_1_4"] = d1 - d4
                    new_feats["demand_growth_ratio_1_2"] = np.clip(np.where(d2 == 0.0, 0.0, (d1 - d2) / (d2 + 1.0)), -5.0, 5.0)
                    new_feats["demand_growth_ratio_1_4"] = np.clip(np.where(d4 == 0.0, 0.0, (d1 - d4) / (d4 + 1.0)), -5.0, 5.0)
                    new_feats["is_zero_denominator_1_2"] = (d2 == 0.0).astype(np.float32)
                    new_feats["is_zero_denominator_1_4"] = (d4 == 0.0).astype(np.float32)
                    new_feats["rolling_cv_8"] = np.where(
                        new_feats["rolling_mean_8"] > 0,
                        new_feats["rolling_std_8"] / (new_feats["rolling_mean_8"] + 1e-4),
                        0.0
                    )

                    for col in origin_carry_cols:
                        new_feats[col] = carry_vals[col]

                    new_feats["weeks_since_last_sale"] = weeks_since_last_sale
                    new_feats["weeks_since_first_observed"] = weeks_since_first_obs
                    new_feats["weeks_since_last_observed_price"] = weeks_since_last_price

                    for i_cal, cal_name in enumerate(CALENDAR_COLUMNS):
                        new_feats[cal_name] = np.full(n_skus, next_cal[i_cal], dtype=np.float32)

                    current_features_df = pd.DataFrame(new_feats, columns=allowlist)

            elif is_tide:
                # TiDE Sequence Model
                model_artifact_id = f"{model_name}_{cohort}"
                ckpt = self.registry.load_model_artifact(model_artifact_id)

                past_tgt = panel.demand_mat[sku_indices, 83:96]
                past_cov = panel.cov_mat[sku_indices, 83:96, :]
                fut_cal = np.tile(fut_cal_mat, (n_skus, 1, 1))

                norm_past_tgt = (past_tgt - ckpt["scaler_target_mean"]) / ckpt["scaler_target_std"]
                norm_past_cov = (past_cov - ckpt["scaler_cov_mean"]) / ckpt["scaler_cov_std"]

                tide_model = TiDESequenceModel(13, 8, 4, 10, 16, 64, 2, 64, 0.1)
                tide_model.load_state_dict(ckpt["state_dict"])
                tide_model.eval()

                with torch.no_grad():
                    preds_norm = tide_model(
                        torch.tensor(norm_past_tgt, dtype=torch.float32),
                        torch.tensor(norm_past_cov, dtype=torch.float32),
                        torch.tensor(fut_cal, dtype=torch.float32)
                    ).numpy()

                pred_raw_mat = preds_norm * ckpt["scaler_target_std"] + ckpt["scaler_target_mean"]
                pred_clip_mat = np.maximum(0.0, pred_raw_mat)

                for h_step in range(1, horizon_weeks + 1):
                    target_week = target_weeks[h_step - 1]
                    step_idx = h_step - 1
                    for i, sku in enumerate(cohort_skus):
                        r_val = float(pred_raw_mat[i, step_idx])
                        c_val = float(pred_clip_mat[i, step_idx])
                        all_records.append({
                            "sku_id": sku,
                            "target_week": target_week,
                            "horizon_step": h_step,
                            "prediction": c_val,
                            "prediction_raw": r_val,
                            "prediction_status": "INFERRED",
                            "clipped_at_zero": 1 if r_val < 0.0 else 0
                        })
            else:
                raise NotImplementedError(f"Model {model_name} inference strategy not implemented.")

        # Sort records by sku_id, horizon_step for deterministic output order
        all_records.sort(key=lambda r: (r["sku_id"], r["horizon_step"]))
        return all_records


# Module-level forecasting service singleton
forecasting_service = ForecastingService()
