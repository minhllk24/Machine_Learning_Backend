"""
Bayesian Optimization module using Optuna for Demand Forecasting models.
Optimizes hyperparameters over expanding window Time-Series Cross-Validation.
"""
import json
import optuna
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

from src.config import (
    OPTUNA_N_TRIALS, OPTUNA_TIMEOUT, RANDOM_SEED,
    MODELS_DIR, TABLES_DIR, logger
)
from src.split import expanding_window_cv
from src.metrics import mae, wape
from src.models.train_lgbm import get_feature_columns

optuna.logging.set_verbosity(optuna.logging.WARNING)


def tune_lgbm_optuna(df_trainval, n_trials=30, timeout=1800, n_folds=3, feature_cols=None):
    """
    Run Optuna Bayesian Optimization for LightGBM.
    
    Parameters
    ----------
    df_trainval : pd.DataFrame
        Training and validation data.
    n_trials : int
        Number of Optuna trials.
    timeout : int
        Max seconds to run.
    n_folds : int
        Number of CV folds to evaluate per trial.
    feature_cols : list, optional
        List of feature column names.
        
    Returns
    -------
    dict
        Best hyperparameters and study object.
    """
    if feature_cols is None:
        feature_cols = get_feature_columns(df_trainval)
        
    logger.info(f"Starting Optuna HPO for LightGBM ({n_trials} trials, {n_folds} folds)...")
    
    folds = expanding_window_cv(df_trainval, n_folds=n_folds)
    
    def objective(trial):
        params = {
            "objective": "regression_l1",  # MAE loss
            "metric": "mae",
            "boosting_type": "gbdt",
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 95),
            "max_depth": trial.suggest_int("max_depth", 3, 9),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "subsample_freq": 1,
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
            "n_estimators": 600,
            "random_state": RANDOM_SEED,
            "verbose": -1,
            "n_jobs": -1,
        }
        
        val_maes = []
        
        for fold_num, (train_idx, val_idx, _) in enumerate(folds):
            df_tr = df_trainval.iloc[train_idx].dropna(subset=["target"])
            df_va = df_trainval.iloc[val_idx].dropna(subset=["target"])
            
            X_tr = df_tr[feature_cols]
            y_tr = df_tr["target"].values
            X_va = df_va[feature_cols]
            y_va = df_va["target"].values
            
            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_va, y_va)],
                callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
            )
            
            preds = np.maximum(0.0, model.predict(X_va))
            fold_mae = mae(y_va, preds)
            val_maes.append(fold_mae)
            
            # Prune unpromising trials
            trial.report(fold_mae, fold_num)
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()
                
        return np.mean(val_maes)

    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, timeout=timeout)
    
    logger.info(f"Optuna HPO completed! Best Trial #{study.best_trial.number}")
    logger.info(f"Best CV MAE: {study.best_value:.4f}")
    logger.info(f"Best Params: {study.best_params}")
    
    # Save best params
    best_params_path = TABLES_DIR / "lgbm_best_hparams.json"
    with open(best_params_path, "w", encoding="utf-8") as f:
        json.dump(study.best_params, f, indent=4)
        
    # Save trial history
    trials_df = study.trials_dataframe()
    trials_df.to_csv(TABLES_DIR / "optuna_trials_history.csv", index=False)
    
    return {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "study": study,
    }
