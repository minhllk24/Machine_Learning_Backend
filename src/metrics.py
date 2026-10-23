"""
Metrics module.
Implements all evaluation metrics for demand forecasting.
"""
import numpy as np
import pandas as pd


def mae(y_true, y_pred):
    """Mean Absolute Error."""
    return np.mean(np.abs(y_true - y_pred))


def rmse(y_true, y_pred):
    """Root Mean Squared Error."""
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def wape(y_true, y_pred):
    """
    Weighted Absolute Percentage Error.
    WAPE = sum(|y - yhat|) / sum(|y|)
    Handles zero demand gracefully.
    """
    total_abs = np.sum(np.abs(y_true))
    if total_abs == 0:
        return np.nan
    return np.sum(np.abs(y_true - y_pred)) / total_abs


def smape(y_true, y_pred):
    """
    Symmetric Mean Absolute Percentage Error.
    sMAPE = mean(2 * |y - yhat| / (|y| + |yhat| + eps))
    """
    eps = 1e-8
    numerator = np.abs(y_true - y_pred)
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2 + eps
    return np.mean(numerator / denominator) * 100


def mase(y_true, y_pred, y_train, seasonality=1):
    """
    Mean Absolute Scaled Error.
    Scaled by the in-sample naive forecast error.
    
    Parameters
    ----------
    y_true : array
        Actual values.
    y_pred : array
        Predicted values.
    y_train : array
        Training data for computing the scaling factor.
    seasonality : int
        Seasonal period for the naive forecast.
    """
    naive_errors = np.abs(np.diff(y_train, n=seasonality))
    if len(naive_errors) == 0:
        return np.nan
    scale = np.mean(naive_errors)
    if scale == 0:
        return np.nan
    return np.mean(np.abs(y_true - y_pred)) / scale


def rmsse(y_true, y_pred, y_train, seasonality=1):
    """
    Root Mean Squared Scaled Error (RMSSE).
    Scaled by the in-sample naive forecast mean squared error.
    
    Parameters
    ----------
    y_true : array
        Actual values.
    y_pred : array
        Predicted values.
    y_train : array
        Training data for computing the scaling factor.
    seasonality : int
        Seasonal period for the naive forecast.
    """
    naive_errors_sq = np.diff(y_train, n=seasonality) ** 2
    if len(naive_errors_sq) == 0:
        return np.nan
    scale_sq = np.mean(naive_errors_sq)
    if scale_sq == 0:
        return np.nan
    mse = np.mean((y_true - y_pred) ** 2)
    return np.sqrt(mse / scale_sq)


def forecast_bias(y_true, y_pred):
    """
    Forecast Bias (normalized).
    Positive = over-forecast, Negative = under-forecast.
    """
    total = np.sum(np.abs(y_true))
    if total == 0:
        return np.nan
    return np.sum(y_pred - y_true) / total


def r_squared(y_true, y_pred):
    """R² (coefficient of determination)."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return np.nan
    return 1 - ss_res / ss_tot


def pinball_loss(y_true, y_pred, quantile):
    """
    Pinball (quantile) loss.
    
    Parameters
    ----------
    quantile : float
        Target quantile (e.g., 0.1, 0.5, 0.9).
    """
    residual = y_true - y_pred
    return np.mean(np.where(residual >= 0, quantile * residual,
                            (quantile - 1) * residual))


def coverage(y_true, lower, upper):
    """
    Prediction Interval Coverage Probability (PICP).
    Fraction of actuals within [lower, upper].
    """
    covered = (y_true >= lower) & (y_true <= upper)
    return np.mean(covered)


def interval_width(lower, upper):
    """Mean Prediction Interval Width (MPIW)."""
    return np.mean(upper - lower)


def compute_all_metrics(y_true, y_pred, y_train=None, prefix=""):
    """
    Compute all point forecast metrics.
    
    Parameters
    ----------
    y_true : array-like
        Actual values.
    y_pred : array-like
        Predicted values.
    y_train : array-like, optional
        Training data for MASE calculation.
    prefix : str
        Optional prefix for metric names.
    
    Returns
    -------
    dict
        Dictionary of metric name → value.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    # Clip predictions to non-negative (demand can't be negative)
    y_pred = np.maximum(y_pred, 0)
    
    results = {
        f"{prefix}MAE": mae(y_true, y_pred),
        f"{prefix}RMSE": rmse(y_true, y_pred),
        f"{prefix}WAPE": wape(y_true, y_pred),
        f"{prefix}sMAPE": smape(y_true, y_pred),
        f"{prefix}Bias": forecast_bias(y_true, y_pred),
        f"{prefix}R2": r_squared(y_true, y_pred),
    }
    
    if y_train is not None:
        y_train = np.asarray(y_train, dtype=float)
        results[f"{prefix}MASE"] = mase(y_true, y_pred, y_train)
        results[f"{prefix}RMSSE"] = rmsse(y_true, y_pred, y_train)
    
    return results


def metrics_to_dataframe(metrics_dict, decimals=4):
    """Convert metrics dictionary to a formatted DataFrame."""
    df = pd.DataFrame([metrics_dict]).T
    df.columns = ["Value"]
    df = df.round(decimals)
    return df
