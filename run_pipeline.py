"""
End-to-End Orchestrator for Machine Learning Demand Forecasting.
Executes the full pipeline:
1. Data Loading & Cleaning
2. SKU-Week Aggregation & Complete Panel Construction
3. Comprehensive EDA & Publication Figures
4. Feature Engineering & Chronological Split
5. Baseline Models Evaluation
6. LightGBM Cross-Validation & Bayesian HPO (Optuna)
7. CatBoost Cross-Validation
8. Final Holdout Evaluation & Statistical Tests
9. Feature Ablation Study
10. SHAP Explainability & Attribution
11. Conformal Prediction Intervals (Uncertainty)
12. Inventory Planning Simulation & Business ROI
"""
import sys
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    RAW_EXCEL, CLEANED_TRANSACTIONS, SKU_WEEK_DEMAND, SKU_WEEK_FEATURES,
    TEST_PREDICTIONS, DATA_DICTIONARY, TABLES_DIR, FIGURES_DIR,
    MODELS_DIR, PREDICTIONS_DIR, RANDOM_SEED, logger
)
from src.data_loader import load_raw_data, data_profile
from src.cleaning import clean_transactions, get_cleaning_summary_table
from src.aggregation import aggregate_to_sku_week, define_active_sku_window, create_complete_panel, save_sku_week_demand
from src.eda import run_eda_pipeline
from src.features import build_all_features
from src.split import chronological_split
from src.models.baseline import evaluate_baselines
from src.models.train_lgbm import get_feature_columns, train_lgbm_cv, train_lgbm_final
from src.models.train_catboost import train_catboost_cv, train_catboost_final
from src.models.hpo import tune_lgbm_optuna
from src.models.evaluate import compare_all_models, paired_statistical_test, segment_error_analysis
from src.explainability import run_shap_analysis
from src.uncertainty import evaluate_conformal_intervals
from src.inventory_sim import compare_inventory_policies
from src.ablation import run_ablation_study


def generate_data_dictionary(features_df):
    """Generate and save the formal data dictionary table."""
    records = []
    for col in features_df.columns:
        dtype = str(features_df[col].dtype)
        if col == "sku_id":
            desc = "Mã định danh sản phẩm bán lẻ (StockCode/SKU)"
            grp = "Identifier"
        elif col == "week_start":
            desc = "Ngày bắt đầu của tuần kinh doanh (thứ Hai, W-MON)"
            grp = "Time"
        elif col == "target":
            desc = "Mục tiêu: Tổng số lượng nhu cầu tuần tiếp theo (t+1)"
            grp = "Target"
        elif col == "demand":
            desc = "Tổng số lượng sản phẩm bán được trong tuần hiện tại (t)"
            grp = "Demand"
        elif "lag_" in col:
            desc = f"Nhu cầu quá khứ trễ {col.split('_')[-1]} tuần"
            grp = "Lag"
        elif "rolling_mean_" in col:
            desc = f"Trung bình trượt nhu cầu {col.split('_')[-1]} tuần qua (dựa trên t-1)"
            grp = "Rolling"
        elif "rolling_std_" in col:
            desc = f"Độ lệch chuẩn trượt nhu cầu {col.split('_')[-1]} tuần qua"
            grp = "Rolling"
        elif "rolling_median_" in col:
            desc = f"Trung vị trượt nhu cầu {col.split('_')[-1]} tuần qua"
            grp = "Rolling"
        elif "ewma_" in col:
            desc = f"Trung bình trượt hàm mũ (EWMA) span={col.split('_')[-1]} tuần"
            grp = "EWM"
        elif "price" in col:
            desc = "Đặc trưng giá bán đơn vị và biến động giá quá khứ"
            grp = "Price"
        elif "txn_" in col or "cust_" in col:
            desc = "Đặc trưng tần suất giao dịch và số lượng khách hàng mua sắm"
            grp = "Activity"
        elif col in ["week_of_year", "month", "quarter", "year", "time_index", "week_sin", "week_cos", "month_sin", "month_cos", "is_december"]:
            desc = "Đặc trưng lịch, chu kỳ tuần/tháng, chỉ số thời gian và mùa vụ lễ hội"
            grp = "Calendar"
        elif "zero_rate" in col or "weeks_since" in col or "intermittency" in col or "cv_" in col or "growth" in col:
            desc = "Đặc trưng động lực nhu cầu, tính gián đoạn (intermittency) và khoảng cách bán hàng"
            grp = "Demand Dynamics"
        elif "total_market" in col or "sku_share" in col:
            desc = "Đặc trưng quy mô thị trường tổng và thị phần của SKU tại t-1"
            grp = "Cross-sectional"
        else:
            desc = "Thuộc tính thống kê hỗ trợ"
            grp = "Other"
            
        records.append({
            "Column_Name": col,
            "Data_Type": dtype,
            "Feature_Group": grp,
            "Description_VN": desc,
            "Sample_Value": str(features_df[col].dropna().iloc[0]) if len(features_df[col].dropna()) > 0 else "N/A"
        })
        
    dict_df = pd.DataFrame(records)
    dict_df.to_csv(DATA_DICTIONARY, index=False)
    logger.info(f"Generated formal data dictionary with {len(dict_df)} columns at {DATA_DICTIONARY}")
    return dict_df


def main():
    start_time = time.time()
    logger.info("============================================================")
    logger.info("STARTING END-TO-END DEMAND FORECASTING ML PIPELINE")
    logger.info("============================================================")
    
    # ------------------------------------------------------------
    # STEP 1: DATA LOADING
    # ------------------------------------------------------------
    if CLEANED_TRANSACTIONS.exists():
        logger.info(f"Found existing cleaned data at {CLEANED_TRANSACTIONS}, reading...")
        df_cleaned = pd.read_parquet(CLEANED_TRANSACTIONS)
        df_raw = None
    else:
        logger.info("Loading raw Online Retail II dataset...")
        df_raw = load_raw_data(RAW_EXCEL)
        profile = data_profile(df_raw)
        with open(TABLES_DIR / "raw_data_profile.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)
        
        # STEP 2: DATA CLEANING
        logger.info("Cleaning transactions...")
        df_cleaned, clean_log = clean_transactions(df_raw, save=True)
        summary_clean_table = get_cleaning_summary_table(clean_log)
        summary_clean_table.to_csv(TABLES_DIR / "cleaning_summary.csv", index=False)
        
    # ------------------------------------------------------------
    # STEP 3: SKU-WEEK AGGREGATION & COMPLETE PANEL
    # ------------------------------------------------------------
    if SKU_WEEK_DEMAND.exists():
        logger.info(f"Loading existing SKU-week panel from {SKU_WEEK_DEMAND}...")
        panel_df = pd.read_csv(SKU_WEEK_DEMAND)
        panel_df["week_start"] = pd.to_datetime(panel_df["week_start"])
    else:
        logger.info("Aggregating to SKU-week level...")
        agg_df = aggregate_to_sku_week(df_cleaned)
        filtered_agg, active_skus, active_log, sku_stats = define_active_sku_window(agg_df)
        with open(TABLES_DIR / "active_sku_filter_log.json", "w", encoding="utf-8") as f:
            json.dump(active_log, f, indent=4)
        sku_stats.to_csv(TABLES_DIR / "sku_lifecycle_stats.csv", index=False)
        
        panel_df = create_complete_panel(filtered_agg, active_skus)
        save_sku_week_demand(panel_df)
        
    # ------------------------------------------------------------
    # STEP 4: EDA PIPELINE
    # ------------------------------------------------------------
    if df_raw is None:
        # Load sample or lightweight view of raw if needed, or pass df_cleaned
        run_eda_pipeline(df_cleaned, df_cleaned, panel_df)
    else:
        run_eda_pipeline(df_raw, df_cleaned, panel_df)
        
    # ------------------------------------------------------------
    # STEP 5: FEATURE ENGINEERING
    # ------------------------------------------------------------
    if SKU_WEEK_FEATURES.exists():
        logger.info(f"Loading existing engineered features from {SKU_WEEK_FEATURES}...")
        features_df = pd.read_parquet(SKU_WEEK_FEATURES)
    else:
        features_df = build_all_features(panel_df, save=True)
        
    features_df["week_start"] = pd.to_datetime(features_df["week_start"])
    
    # Generate data dictionary
    generate_data_dictionary(features_df)
    
    # ------------------------------------------------------------
    # STEP 6: CHRONOLOGICAL SPLIT
    # ------------------------------------------------------------
    df_trainval, df_test, split_info = chronological_split(features_df, test_weeks=8)
    with open(TABLES_DIR / "train_test_split_info.json", "w", encoding="utf-8") as f:
        json.dump(split_info, f, indent=4)
    
    feature_cols = get_feature_columns(df_trainval)
    logger.info(f"Total features for modeling: {len(feature_cols)}")
    
    y_test = df_test["target"].values
    y_train_full = df_trainval["target"].dropna().values
    
    # ------------------------------------------------------------
    # STEP 7: BASELINE MODELS EVALUATION
    # ------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("EVALUATING BASELINES ON TEST SET")
    logger.info("=" * 60)
    baseline_summary, baseline_preds = evaluate_baselines(df_test, target_col="target", y_train_full=y_train_full)
    baseline_summary.to_csv(TABLES_DIR / "baseline_comparison.csv")
    
    predictions_dict = {}
    for col in baseline_preds.columns:
        if col != "actual":
            predictions_dict[col] = baseline_preds[col].values
            
    # ------------------------------------------------------------
    # STEP 8: OPTUNA BAYESIAN HPO FOR LIGHTGBM
    # ------------------------------------------------------------
    hpo_path = TABLES_DIR / "lgbm_best_hparams.json"
    if hpo_path.exists():
        logger.info(f"Found existing HPO params at {hpo_path}, loading...")
        with open(hpo_path, "r", encoding="utf-8") as f:
            best_lgbm_params = json.load(f)
    else:
        logger.info("Running Optuna HPO...")
        hpo_res = tune_lgbm_optuna(df_trainval, n_trials=25, timeout=1200, n_folds=3, feature_cols=feature_cols)
        best_lgbm_params = hpo_res["best_params"]
        
    # ------------------------------------------------------------
    # STEP 9: LIGHTGBM TRAINING (DEFAULT & TUNED) WITH TIME-SERIES CV
    # ------------------------------------------------------------
    logger.info("Evaluating default LightGBM with 5-fold CV...")
    lgbm_default_cv = train_lgbm_cv(df_trainval, params=None, n_folds=5, feature_cols=feature_cols)
    lgbm_default_cv["cv_summary"].to_csv(TABLES_DIR / "lgbm_default_cv_scores.csv", index=False)
    
    logger.info("Evaluating tuned LightGBM with 5-fold CV...")
    lgbm_tuned_cv = train_lgbm_cv(df_trainval, params=best_lgbm_params, n_folds=5, feature_cols=feature_cols)
    lgbm_tuned_cv["cv_summary"].to_csv(TABLES_DIR / "lgbm_tuned_cv_scores.csv", index=False)
    lgbm_tuned_cv["feature_importances"].to_csv(TABLES_DIR / "lgbm_feature_importances.csv", index=False)
    
    # Final LightGBM on hold-out Test
    lgbm_final_res = train_lgbm_final(
        df_trainval, df_test,
        params=best_lgbm_params,
        feature_cols=feature_cols,
        best_iteration=int(lgbm_tuned_cv["cv_summary"]["best_iteration"].median())
    )
    predictions_dict["LightGBM (Tuned)"] = lgbm_final_res["predictions"]["pred_lgbm"].values
    
    # ------------------------------------------------------------
    # STEP 10: CATBOOST TRAINING WITH TIME-SERIES CV & TEST
    # ------------------------------------------------------------
    logger.info("Evaluating CatBoost with 5-fold CV...")
    cb_cv = train_catboost_cv(df_trainval, n_folds=3, feature_cols=feature_cols)
    cb_cv["cv_summary"].to_csv(TABLES_DIR / "catboost_cv_scores.csv", index=False)
    
    cb_final_res = train_catboost_final(
        df_trainval, df_test,
        feature_cols=feature_cols,
        best_iteration=int(cb_cv["cv_summary"]["best_iteration"].median())
    )
    predictions_dict["CatBoost"] = cb_final_res["predictions"]["pred_catboost"].values
    
    # ------------------------------------------------------------
    # STEP 11: MODEL COMPARISON & STATISTICAL SIGNIFICANCE TESTS
    # ------------------------------------------------------------
    logger.info("Building Model Leaderboard...")
    leaderboard = compare_all_models(predictions_dict, y_test, y_train=y_train_full)
    leaderboard.to_csv(TABLES_DIR / "model_comparison_leaderboard.csv", index=False)
    logger.info("\n" + leaderboard.to_string(index=False))
    
    # Statistical test: LightGBM vs Naive and vs CatBoost
    lgbm_preds = predictions_dict["LightGBM (Tuned)"]
    naive_preds = predictions_dict["Naive (t-1)"]
    cb_preds = predictions_dict["CatBoost"]
    
    test_vs_naive = paired_statistical_test(lgbm_preds - y_test, naive_preds - y_test)
    test_vs_cb = paired_statistical_test(lgbm_preds - y_test, cb_preds - y_test)
    
    stat_tests_df = pd.DataFrame([
        {"Comparison": "LightGBM vs Naive (t-1)", **test_vs_naive},
        {"Comparison": "LightGBM vs CatBoost", **test_vs_cb},
    ])
    stat_tests_df.to_csv(TABLES_DIR / "statistical_tests.csv", index=False)
    logger.info("Statistical Significance Tests:")
    logger.info(stat_tests_df.to_string(index=False))
    
    # Demand Segment Error Analysis
    eval_df = df_test.copy()
    eval_df["pred_lgbm"] = lgbm_preds
    segment_df = segment_error_analysis(eval_df, pred_col="pred_lgbm", target_col="target")
    segment_df.to_csv(TABLES_DIR / "demand_segment_error_breakdown.csv", index=False)
    
    # ------------------------------------------------------------
    # STEP 12: SHAP EXPLAINABILITY
    # ------------------------------------------------------------
    logger.info("Running SHAP Analysis...")
    shap_res = run_shap_analysis(lgbm_final_res["model"], df_test, feature_cols)
    
    # ------------------------------------------------------------
    # STEP 13: UNCERTAINTY QUANTIFICATION (CONFORMAL PREDICTION)
    # ------------------------------------------------------------
    logger.info("Running Split Conformal Prediction for Uncertainty Intervals...")
    # Use OOF predictions from last fold as calibration set
    calib_df = lgbm_tuned_cv["oof_predictions"]
    y_calib_true = calib_df["target"].values
    y_calib_pred = calib_df["pred_lgbm"].values
    
    conf_summary, intervals = evaluate_conformal_intervals(
        y_test, lgbm_preds, y_calib_true, y_calib_pred,
        alphas=[0.20, 0.10, 0.05]
    )
    
    # Add intervals to final predictions
    pred_save_df = lgbm_final_res["predictions"].copy()
    pred_save_df["lower_90"] = intervals["90%"][0]
    pred_save_df["upper_90"] = intervals["90%"][1]
    pred_save_df["lower_80"] = intervals["80%"][0]
    pred_save_df["upper_80"] = intervals["80%"][1]
    pred_save_df["pred_catboost"] = cb_preds
    pred_save_df["pred_naive"] = naive_preds
    pred_save_df.to_csv(TEST_PREDICTIONS, index=False)
    logger.info(f"Saved complete test predictions to {TEST_PREDICTIONS}")
    
    # ------------------------------------------------------------
    # STEP 14: INVENTORY PLANNING SIMULATION
    # ------------------------------------------------------------
    logger.info("Running Inventory Policy Simulation...")
    sim_models = ["Naive (t-1)", "SMA (4 weeks)", "CatBoost", "LightGBM (Tuned)"]
    sim_input_df = df_test.copy()
    for m_name in sim_models:
        sim_input_df[m_name] = predictions_dict[m_name]
        
    inv_sim_df = compare_inventory_policies(sim_input_df, model_cols=sim_models, target_col="target")
    
    # ------------------------------------------------------------
    # STEP 15: FEATURE GROUP ABLATION STUDY
    # ------------------------------------------------------------
    logger.info("Running Feature Group Ablation Study...")
    ablation_df = run_ablation_study(df_trainval, base_params=best_lgbm_params, n_folds=3)
    
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"END-TO-END PIPELINE COMPLETED IN {elapsed/60:.2f} MINUTES")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
