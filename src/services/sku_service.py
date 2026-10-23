"""
SKU Service for Retail SKU-Week Demand Forecasting.
Provides catalog exploration, metadata inspection, and historical time-series queries.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.core.config import settings
from src.core.logging_config import logger
from src.api.errors import SKUNotFoundException
from src.api.schemas.skus import (
    SKUSummary,
    SKUListResponse,
    SKUDetailResponse,
    SKUHistoryPoint,
    SKUHistoryResponse,
)
from src.models.sequence_dataset import PanelDataContainer


class SKUService:
    """Service handling catalog lookup, metadata enrichment, and demand history queries."""

    def __init__(self, panel: Optional[PanelDataContainer] = None):
        self._panel = panel
        self._metadata_df: Optional[pd.DataFrame] = None
        self._sku_dict: Optional[Dict[str, Dict[str, Any]]] = None

    def _ensure_initialized(self):
        if self._metadata_df is None:
            if self._panel is None:
                self._panel = PanelDataContainer()

            logger.info("Initializing SKUService catalog indices and summary metrics...")
            panel = self._panel
            skus = panel.all_skus
            n_skus = len(skus)

            # Load EDA cross and SBC tables if available
            cross_path = settings.TABLES_DIR / "eda_abc_xyz_cross.csv"
            sbc_p_path = settings.TABLES_DIR / "eda_sbc_primary.csv"
            sbc_s_path = settings.TABLES_DIR / "eda_sbc_secondary.csv"

            cross_df = pd.read_csv(cross_path, dtype={"sku_id": str}) if cross_path.exists() else None
            sbc_p = pd.read_csv(sbc_p_path, dtype={"sku_id": str}) if sbc_p_path.exists() else None
            sbc_s = pd.read_csv(sbc_s_path, dtype={"sku_id": str}) if sbc_s_path.exists() else None

            # Merge SBC tables
            sbc_combined = None
            if sbc_p is not None and sbc_s is not None:
                sbc_combined = pd.concat([sbc_p, sbc_s]).drop_duplicates(subset=["sku_id"]).set_index("sku_id")
            elif sbc_p is not None:
                sbc_combined = sbc_p.set_index("sku_id")

            if cross_df is not None:
                cross_indexed = cross_df.drop_duplicates(subset=["sku_id"]).set_index("sku_id")
            else:
                cross_indexed = None

            # Matrix statistics
            tot_demand = np.sum(panel.demand_mat, axis=1)
            avg_demand = np.mean(panel.demand_mat, axis=1)
            zero_count = np.sum(panel.demand_mat == 0.0, axis=1)
            active_count = panel.n_weeks - zero_count
            zero_ratio = zero_count / float(panel.n_weeks)
            last_price = panel.cov_mat[:, -1, 0]  # channel 0 is price at week 95

            sku_rows = []
            for i, sku in enumerate(skus):
                cohort = panel.sku_cohort_map.get(sku, "CAUSAL_MATURE")
                
                # Descriptors
                abc_d = None
                abc_v = None
                xyz_v = None
                if cross_indexed is not None and sku in cross_indexed.index:
                    abc_d = str(cross_indexed.loc[sku, "abc_demand_class"])
                    abc_v = str(cross_indexed.loc[sku, "abc_value_class_panel"])
                    xyz_v = str(cross_indexed.loc[sku, "xyz_variability_class"])

                sbc_reg = None
                adi = None
                cv2 = None
                if sbc_combined is not None and sku in sbc_combined.index:
                    sbc_reg = str(sbc_combined.loc[sku, "sbc_regime"])
                    if "adi" in sbc_combined.columns:
                        adi = float(sbc_combined.loc[sku, "adi"])
                    if "cv2" in sbc_combined.columns:
                        cv2 = float(sbc_combined.loc[sku, "cv2"])

                sku_rows.append({
                    "sku_id": sku,
                    "cohort_tier": cohort,
                    "abc_demand_class": abc_d,
                    "abc_value_class": abc_v,
                    "xyz_variability_class": xyz_v,
                    "sbc_regime": sbc_reg,
                    "adi": round(adi, 2) if adi is not None else None,
                    "cv2": round(cv2, 4) if cv2 is not None else None,
                    "total_demand_units": round(float(tot_demand[i]), 1),
                    "avg_weekly_demand": round(float(avg_demand[i]), 2),
                    "zero_weeks_count": int(zero_count[i]),
                    "active_weeks_count": int(active_count[i]),
                    "intermittency_ratio": round(float(zero_ratio[i]), 4),
                    "last_observed_price": round(float(last_price[i]), 2) if last_price[i] > 0 else None,
                    "first_observed_week": panel.weeks[0],
                    "last_observed_week": panel.weeks[-1],
                    "total_weeks_in_catalog": panel.n_weeks,
                    "matrix_index": i
                })

            self._metadata_df = pd.DataFrame(sku_rows)
            self._sku_dict = {row["sku_id"]: row for row in sku_rows}
            logger.info(f"SKUService catalog indexed: {len(self._sku_dict)} SKUs.")

    def list_skus(
        self,
        page: int = 1,
        page_size: int = 50,
        cohort: Optional[str] = None,
        search: Optional[str] = None,
        abc_class: Optional[str] = None,
        sbc_regime: Optional[str] = None,
    ) -> SKUListResponse:
        self._ensure_initialized()
        df = self._metadata_df

        if cohort:
            df = df[df["cohort_tier"].str.upper() == cohort.upper()]
        if abc_class:
            df = df[df["abc_demand_class"].str.upper() == abc_class.upper()]
        if sbc_regime:
            df = df[df["sbc_regime"].str.lower() == sbc_regime.lower()]
        if search:
            df = df[df["sku_id"].str.contains(search, case=False, na=False)]

        total = len(df)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        items = [
            SKUSummary(
                sku_id=r["sku_id"],
                cohort_tier=r["cohort_tier"],
                abc_demand_class=r["abc_demand_class"],
                abc_value_class=r["abc_value_class"],
                xyz_variability_class=r["xyz_variability_class"],
                sbc_regime=r["sbc_regime"],
                total_demand_units=r["total_demand_units"],
                avg_weekly_demand=r["avg_weekly_demand"],
                zero_weeks_count=r["zero_weeks_count"],
                active_weeks_count=r["active_weeks_count"],
                intermittency_ratio=r["intermittency_ratio"],
                last_observed_price=r["last_observed_price"]
            )
            for _, r in page_df.iterrows()
        ]

        return SKUListResponse(total=total, page=page, page_size=page_size, items=items)

    def get_sku_detail(self, sku_id: str) -> SKUDetailResponse:
        self._ensure_initialized()
        data = self._sku_dict.get(sku_id)
        if not data:
            raise SKUNotFoundException(sku_id)

        return SKUDetailResponse(
            sku_id=data["sku_id"],
            cohort_tier=data["cohort_tier"],
            abc_demand_class=data["abc_demand_class"],
            abc_value_class=data["abc_value_class"],
            xyz_variability_class=data["xyz_variability_class"],
            sbc_regime=data["sbc_regime"],
            adi=data["adi"],
            cv2=data["cv2"],
            first_observed_week=data["first_observed_week"],
            last_observed_week=data["last_observed_week"],
            total_weeks_in_catalog=data["total_weeks_in_catalog"],
            total_demand_units=data["total_demand_units"],
            avg_weekly_demand=data["avg_weekly_demand"],
            zero_demand_weeks=data["zero_weeks_count"],
            zero_rate=data["intermittency_ratio"],
            latest_unit_price=data["last_observed_price"],
            serving_eligible=True
        )

    def get_sku_history(self, sku_id: str) -> SKUHistoryResponse:
        self._ensure_initialized()
        data = self._sku_dict.get(sku_id)
        if not data:
            raise SKUNotFoundException(sku_id)

        idx = data["matrix_index"]
        panel = self._panel

        d_row = panel.demand_mat[idx]
        cov_row = panel.cov_mat[idx]  # price, txn, cust, zero

        points = []
        for t, week in enumerate(panel.weeks):
            points.append(
                SKUHistoryPoint(
                    week_start=week,
                    demand=float(d_row[t]),
                    avg_unit_price=round(float(cov_row[t, 0]), 2),
                    transaction_count=int(cov_row[t, 1]),
                    unique_customer_count=int(cov_row[t, 2]),
                    zero_demand_flag=int(cov_row[t, 3])
                )
            )

        return SKUHistoryResponse(
            sku_id=sku_id,
            cohort_tier=data["cohort_tier"],
            total_weeks=len(points),
            history=points
        )


# Singleton instance
sku_service = SKUService()
