"""
Uncertainty Quantification and Conformal Prediction Module.
Implements Split Conformal Prediction to produce calibrated prediction intervals
[y_lower, y_upper] for risk-aware safety stock and inventory planning.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from src.config import FIGURES_DIR, TABLES_DIR, logger
from src.metrics import coverage, interval_width


class ConformalPredictor:
    """
    Split Conformal Prediction for time-series point forecast calibration.
    Computes conformity non-conformity scores s_i = |y_i - y_hat_i| on calibration set
    to guarantee finite-sample coverage probability >= 1 - alpha.
    """
    
    def __init__(self, alpha=0.10):
        """
        Parameters
        ----------
        alpha : float
            Significance level (e.g., alpha=0.10 for 90% confidence interval).
        """
        self.alpha = alpha
        self.q_val = None
        
    def calibrate(self, y_true_calib, y_pred_calib):
        """
        Calibrate prediction interval margin on held-out calibration set.
        """
        residuals = np.abs(y_true_calib - y_pred_calib)
        n = len(residuals)
        # Quantile index with finite-sample correction: ceil((n+1)(1-alpha)) / n
        q_level = min(1.0, np.ceil((n + 1) * (1 - self.alpha)) / n)
        self.q_val = np.quantile(residuals, q_level)
        logger.info(f"Conformal Calibration (1-alpha={1-self.alpha:.2f}): non-conformity quantile q={self.q_val:.4f}")
        return self
        
    def predict_interval(self, y_pred):
        """
        Produce [lower, upper] interval for point predictions.
        Lower bound truncated at 0 (non-negative retail demand).
        """
        if self.q_val is None:
            raise ValueError("Predictor must be calibrated before predicting intervals.")
            
        lower = np.maximum(0.0, y_pred - self.q_val)
        upper = y_pred + self.q_val
        return lower, upper


def evaluate_conformal_intervals(y_true, y_pred, y_calib_true, y_calib_pred, alphas=[0.20, 0.10, 0.05]):
    """
    Calibrate and evaluate conformal intervals across multiple coverage levels.
    """
    results = []
    intervals_dict = {}
    
    for alpha in alphas:
        nominal_coverage = 1.0 - alpha
        cp = ConformalPredictor(alpha=alpha)
        cp.calibrate(y_calib_true, y_calib_pred)
        
        lower, upper = cp.predict_interval(y_pred)
        emp_cov = coverage(y_true, lower, upper)
        mean_width = interval_width(lower, upper)
        
        results.append({
            "Confidence_Level": f"{nominal_coverage*100:.0f}%",
            "Nominal_Coverage": nominal_coverage,
            "Empirical_Coverage": emp_cov,
            "Margin_q": cp.q_val,
            "Mean_Interval_Width": mean_width,
        })
        intervals_dict[f"{nominal_coverage*100:.0f}%"] = (lower, upper)
        
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(TABLES_DIR / "conformal_prediction_intervals.csv", index=False)
    logger.info("Conformal Intervals Summary:")
    for _, row in summary_df.iterrows():
        logger.info(f"  {row['Confidence_Level']}: Empirical Coverage = {row['Empirical_Coverage']*100:.1f}%, Width = {row['Mean_Interval_Width']:.2f}")
        
    return summary_df, intervals_dict
