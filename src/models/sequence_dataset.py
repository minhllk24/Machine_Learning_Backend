from pathlib import Path
"""
Sequence Dataset and Window Generator for Canonical Temporal Models.
Retail SKU-Week Demand Forecasting & Inventory Planning.

Implements causal temporal window extraction:
- Lookback window: L time steps (default L=13 weeks)
- Forecast horizon: H time steps (default H=8 weeks)
- Dynamic past covariates: (price, transaction count, customer count, zero demand flag)
- Known future calendar covariates: 10 deterministic calendar features
- Strict temporal isolation: zero future target leakage, scaler fit strictly on training slices.
"""
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
try:
    import torch
    from torch.utils.data import Dataset, DataLoader
except ImportError:
    torch = None
    class Dataset:  # type: ignore
        pass
    class DataLoader:  # type: ignore
        pass


CALENDAR_COLUMNS = [
    "target_week_of_year",
    "target_month",
    "target_quarter",
    "target_week_sin",
    "target_week_cos",
    "target_month_sin",
    "target_month_cos",
    "target_is_december",
    "target_is_q4",
    "target_weeks_to_christmas"
]


class TemporalSequenceDataset(Dataset):
    """
    PyTorch Dataset for canonical temporal models (TiDE_Sequence_v1, TFT_Sequence_v1).
    """
    def __init__(
        self,
        past_targets: np.ndarray,
        past_covariates: np.ndarray,
        past_calendar: np.ndarray,
        future_calendar: np.ndarray,
        future_targets: Optional[np.ndarray] = None,
        sku_indices: Optional[np.ndarray] = None,
        origin_indices: Optional[np.ndarray] = None
    ):
        self.past_targets = torch.tensor(past_targets, dtype=torch.float32)
        self.past_covariates = torch.tensor(past_covariates, dtype=torch.float32)
        self.past_calendar = torch.tensor(past_calendar, dtype=torch.float32)
        self.future_calendar = torch.tensor(future_calendar, dtype=torch.float32)
        if future_targets is not None:
            self.future_targets = torch.tensor(future_targets, dtype=torch.float32)
        else:
            self.future_targets = None
        self.sku_indices = sku_indices
        self.origin_indices = origin_indices

    def __len__(self) -> int:
        return len(self.past_targets)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = {
            "past_targets": self.past_targets[idx],
            "past_covariates": self.past_covariates[idx],
            "past_calendar": self.past_calendar[idx],
            "future_calendar": self.future_calendar[idx],
        }
        if self.future_targets is not None:
            item["future_targets"] = self.future_targets[idx]
        return item


class PanelDataContainer:
    """
    In-memory representation of development panel data pivoted for vectorized sequence extraction.
    """
    def __init__(
        self,
        demand_csv_path: str = "data/processed/sku_week_demand_v1_1.csv",
        features_parquet_path: str = "data/processed/sku_week_features_v1_2_dev.parquet"
    ):
        self.demand_csv_path = demand_csv_path
        self.features_parquet_path = features_parquet_path
        self._load_and_pivot()

    def _load_and_pivot(self):
        # 1. Load demand and filter to development pool
        df_demand = pd.read_csv(self.demand_csv_path, low_memory=False)
        dev_demand = df_demand[
            df_demand["period_role"].isin(["TRAIN_VALIDATION_POOL", "HOLIDAY_ZERO_DEMAND"])
        ].copy()

        # Sort weeks chronologically
        self.weeks = sorted(dev_demand["week_start"].unique().tolist())
        self.week_to_idx = {w: i for i, w in enumerate(self.weeks)}
        self.n_weeks = len(self.weeks)  # 96 weeks

        # SKU metadata and ordering
        sku_meta = dev_demand[["sku_id", "cohort_tier"]].drop_duplicates().sort_values("sku_id")
        self.all_skus = sku_meta["sku_id"].tolist()
        self.sku_cohort_map = dict(zip(sku_meta["sku_id"], sku_meta["cohort_tier"]))
        self.sku_to_idx = {sku: i for i, sku in enumerate(self.all_skus)}
        self.n_skus = len(self.all_skus)

        # Pivot matrices: shape (n_skus, n_weeks)
        piv_demand = dev_demand.pivot(index="sku_id", columns="week_start", values="demand").reindex(
            index=self.all_skus, columns=self.weeks
        ).fillna(0.0)
        piv_price = dev_demand.pivot(index="sku_id", columns="week_start", values="avg_unit_price").reindex(
            index=self.all_skus, columns=self.weeks
        ).fillna(0.0)
        piv_txn = dev_demand.pivot(index="sku_id", columns="week_start", values="transaction_count").reindex(
            index=self.all_skus, columns=self.weeks
        ).fillna(0.0)
        piv_cust = dev_demand.pivot(index="sku_id", columns="week_start", values="unique_customer_count").reindex(
            index=self.all_skus, columns=self.weeks
        ).fillna(0.0)
        piv_zero = dev_demand.pivot(index="sku_id", columns="week_start", values="zero_demand_flag").reindex(
            index=self.all_skus, columns=self.weeks
        ).fillna(1.0)

        self.demand_mat = piv_demand.values.astype(np.float32)  # (2785, 96)

        # Dynamic covariates: 4 channels (price, txn, cust, zero_flag)
        self.cov_mat = np.stack([
            piv_price.values.astype(np.float32),
            piv_txn.values.astype(np.float32),
            piv_cust.values.astype(np.float32),
            piv_zero.values.astype(np.float32)
        ], axis=-1)  # (2785, 96, 4)

        del piv_demand, piv_price, piv_txn, piv_cust, piv_zero, dev_demand
        import gc
        gc.collect()

        # 2. Load 10 calendar covariates from compact 96-week CSV (if available) or selective Parquet columns
        compact_cal = Path(self.features_parquet_path).parent / "calendar_covariates_96weeks.csv"
        if compact_cal.exists():
            cal_df = pd.read_csv(compact_cal).set_index("target_week").reindex(self.weeks)
        else:
            df_feat = pd.read_parquet(self.features_parquet_path, columns=["target_week"] + CALENDAR_COLUMNS)
            cal_df = df_feat[["target_week"] + CALENDAR_COLUMNS].drop_duplicates().set_index("target_week").reindex(self.weeks)
            del df_feat
            gc.collect()
        self.cal_mat = cal_df.values.astype(np.float32)  # (96, 10)

    def get_cohort_sku_indices(self, cohort: str) -> np.ndarray:
        """Returns array of row indices in panel matrix for the specified cohort."""
        return np.array([
            i for i, sku in enumerate(self.all_skus)
            if self.sku_cohort_map[sku] == cohort
        ], dtype=np.int64)

    def extract_windows(
        self,
        cohort: str,
        origin_indices: List[int],
        lookback_len: int = 13,
        horizon_len: int = 8,
        include_targets: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], np.ndarray, np.ndarray]:
        """
        Vectorized window extraction across specified origins and cohort SKUs.
        
        Args:
            cohort: "CAUSAL_MATURE" or "LATE_MATURING"
            origin_indices: List of integer week indices representing forecast origins t
            lookback_len: L (lookback weeks ending at t)
            horizon_len: H (horizon weeks starting at t+1)
            include_targets: Whether to extract future targets (True for training, False for pure inference)
            
        Returns:
            past_targets: (num_samples, L)
            past_covs: (num_samples, L, 4)
            past_cal: (num_samples, L, 10)
            fut_cal: (num_samples, H, 10)
            fut_targets: (num_samples, H) or None
            sku_ids: (num_samples,)
            origin_weeks: (num_samples,)
        """
        sku_idxs = self.get_cohort_sku_indices(cohort)
        n_cohort_skus = len(sku_idxs)
        cohort_demand = self.demand_mat[sku_idxs]  # (n_cohort_skus, 96)
        cohort_cov = self.cov_mat[sku_idxs]        # (n_cohort_skus, 96, 4)

        past_t_list, past_c_list, past_cal_list, fut_cal_list, fut_t_list = [], [], [], [], []
        sku_list, orig_list = [], []

        for t in origin_indices:
            assert t - lookback_len + 1 >= 0, f"Origin index {t} too early for lookback {lookback_len}"

            # Past target: (n_skus, L)
            p_t = cohort_demand[:, t - lookback_len + 1 : t + 1]
            # Past dynamic cov: (n_skus, L, 4)
            p_c = cohort_cov[:, t - lookback_len + 1 : t + 1, :]
            # Past calendar: (n_skus, L, 10)
            p_cal = np.tile(self.cal_mat[t - lookback_len + 1 : t + 1, :], (n_cohort_skus, 1, 1))

            # Future calendar: handle boundary by clamping index to valid weeks
            fut_indices = np.clip(np.arange(t + 1, t + horizon_len + 1), 0, self.n_weeks - 1)
            f_cal = np.tile(self.cal_mat[fut_indices, :], (n_cohort_skus, 1, 1))

            past_t_list.append(p_t)
            past_c_list.append(p_c)
            past_cal_list.append(p_cal)
            fut_cal_list.append(f_cal)

            if include_targets:
                valid_fut_indices = [idx for idx in range(t + 1, t + horizon_len + 1) if idx < self.n_weeks]
                f_t_valid = cohort_demand[:, valid_fut_indices]
                if len(valid_fut_indices) < horizon_len:
                    pad_len = horizon_len - len(valid_fut_indices)
                    f_t_pad = np.zeros((n_cohort_skus, pad_len), dtype=np.float32)
                    f_t = np.concatenate([f_t_valid, f_t_pad], axis=1)
                else:
                    f_t = f_t_valid
                fut_t_list.append(f_t)

            sku_list.append([self.all_skus[i] for i in sku_idxs])
            orig_list.append([self.weeks[t]] * n_cohort_skus)

        # Stack across all origins
        past_targets = np.concatenate(past_t_list, axis=0)  # (N * len(origins), L)
        past_covs = np.concatenate(past_c_list, axis=0)
        past_cal = np.concatenate(past_cal_list, axis=0)
        fut_cal = np.concatenate(fut_cal_list, axis=0)
        fut_targets = np.concatenate(fut_t_list, axis=0) if include_targets else None
        all_skus = np.concatenate(sku_list, axis=0)
        all_origins = np.concatenate(orig_list, axis=0)

        return past_targets, past_covs, past_cal, fut_cal, fut_targets, all_skus, all_origins


class TemporalFeatureScaler:
    """
    Standardizes past targets and dynamic covariates fitted strictly on training slices.
    Prevents temporal leakage across validation folds.
    """
    def __init__(self):
        self.target_mean = 0.0
        self.target_std = 1.0
        self.cov_mean = None
        self.cov_std = None

    def fit(self, past_targets: np.ndarray, past_covs: np.ndarray):
        # Target scaling
        self.target_mean = np.float32(np.mean(past_targets))
        self.target_std = np.float32(np.std(past_targets))
        if self.target_std < 1e-4:
            self.target_std = np.float32(1.0)

        # Covariates scaling across (samples, timesteps, channels)
        self.cov_mean = np.mean(past_covs, axis=(0, 1), keepdims=True).astype(np.float32)  # (1, 1, 4)
        self.cov_std = np.std(past_covs, axis=(0, 1), keepdims=True).astype(np.float32)
        self.cov_std[self.cov_std < 1e-4] = np.float32(1.0)

    def transform(
        self,
        past_targets: np.ndarray,
        past_covs: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        t_scaled = (past_targets - self.target_mean) / self.target_std
        c_scaled = (past_covs - self.cov_mean) / self.cov_std
        return t_scaled.astype(np.float32), c_scaled.astype(np.float32)

    def inverse_transform_targets(self, targets: np.ndarray) -> np.ndarray:
        return (targets * self.target_std) + self.target_mean
