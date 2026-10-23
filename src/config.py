"""
Central configuration for the Demand Forecasting project.
All paths, parameters, and constants are defined here.
"""
import os
from pathlib import Path

# ============================================================
# PATHS
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
PREDICTIONS_DIR = ARTIFACTS_DIR / "predictions"
FIGURES_DIR = ARTIFACTS_DIR / "figures"
TABLES_DIR = ARTIFACTS_DIR / "tables"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Ensure directories exist
for d in [RAW_DIR, INTERIM_DIR, PROCESSED_DIR, MODELS_DIR,
          PREDICTIONS_DIR, FIGURES_DIR, TABLES_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# DATA FILES
# ============================================================
RAW_EXCEL = RAW_DIR / "online_retail_II.xlsx"
CLEANED_TRANSACTIONS = INTERIM_DIR / "cleaned_transactions.parquet"
CLEANED_TRANSACTIONS_ALL = INTERIM_DIR / "cleaned_transactions_all.parquet"
CLEANED_TRANSACTIONS_UK = INTERIM_DIR / "cleaned_transactions_uk.parquet"
SKU_WEEK_DEMAND = PROCESSED_DIR / "sku_week_demand.csv"
SKU_WEEK_DEMAND_V1_1 = PROCESSED_DIR / "sku_week_demand_v1_1.csv"
SKU_WEEK_FEATURES = PROCESSED_DIR / "sku_week_features.parquet"
SKU_WEEK_FEATURES_V1_2_DEV = PROCESSED_DIR / "sku_week_features_v1_2_dev.parquet"
FEATURE_MANIFEST_V1_2 = PROCESSED_DIR / "feature_manifest_v1_2.json"
TRAIN_VAL_TEST_SPLIT_V1_1 = PROCESSED_DIR / "train_val_test_split_v1_1.json"
CALENDAR_WEEK_AUDIT = TABLES_DIR / "calendar_week_audit.csv"
TEST_PREDICTIONS = PROCESSED_DIR / "test_predictions.csv"
DATA_DICTIONARY = PROCESSED_DIR / "data_dictionary.csv"

# ============================================================
# RANDOM SEEDS
# ============================================================
RANDOM_SEED = 42
SEED_LIST = [42, 123, 2024]  # For multi-seed stability check

# ============================================================
# DATA PARAMETERS
# ============================================================
# Country filter: will be decided after EDA
# Set to None to use all countries, or 'United Kingdom' to filter
COUNTRY_FILTER = None  # Decided during EDA

# Active SKU window: minimum number of weeks with sales to consider active
MIN_ACTIVE_WEEKS = 10  # SKU must have sold in >= 10 distinct weeks
MIN_TOTAL_DEMAND = 50  # SKU must have total demand >= 50 units
MAX_GAP_WEEKS = 8      # Maximum consecutive zero-demand weeks before considered inactive

# ============================================================
# TIME PARAMETERS
# ============================================================
FORECAST_HORIZON = 1   # Primary: 1 week ahead
FREQ = "W-MON"         # Weekly frequency, weeks start on Monday

# Train/Validation/Test split (chronological)
# Dataset spans roughly Dec 2009 - Dec 2011 (~104 weeks)
# Test: last 8 weeks
# Validation: 5-fold expanding window CV on remaining
TEST_WEEKS = 8
CV_FOLDS = 5
CV_MIN_TRAIN_WEEKS = 30  # Minimum training weeks in first CV fold

# ============================================================
# FEATURE PARAMETERS
# ============================================================
LAG_WEEKS = [1, 2, 3, 4, 8, 13, 26, 52]
ROLLING_WINDOWS = [4, 8, 13, 26]
EWMA_SPANS = [4, 13]  # Short-term and long-term

# ============================================================
# MODEL PARAMETERS (defaults, will be tuned)
# ============================================================
LGBM_DEFAULT = {
    "objective": "regression",
    "metric": "mae",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "max_depth": -1,
    "learning_rate": 0.05,
    "n_estimators": 1000,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": RANDOM_SEED,
    "verbose": -1,
    "n_jobs": -1,
}

CATBOOST_DEFAULT = {
    "iterations": 1000,
    "learning_rate": 0.05,
    "depth": 8,
    "l2_leaf_reg": 3.0,
    "random_seed": RANDOM_SEED,
    "verbose": 0,
    "loss_function": "MAE",
    "eval_metric": "MAE",
}

# ============================================================
# OPTUNA / BAYESIAN OPTIMIZATION
# ============================================================
OPTUNA_N_TRIALS = 80
OPTUNA_TIMEOUT = 3600  # 1 hour max
OPTUNA_SEED = RANDOM_SEED

# ============================================================
# METRICS
# ============================================================
PRIMARY_METRIC = "MAE"
SECONDARY_METRICS = ["RMSE", "WAPE", "sMAPE", "MASE", "Bias", "R2"]

# ============================================================
# SHAP
# ============================================================
SHAP_MAX_SAMPLES = 2000  # Max samples for SHAP computation
SHAP_TOP_N_FEATURES = 20

# ============================================================
# LOGGING
# ============================================================
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("demand_forecasting")
