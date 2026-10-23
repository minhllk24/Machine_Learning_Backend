"""
Exploratory Data Analysis (EDA) Module.
Generates comprehensive descriptive statistics and figures for the retail demand forecasting project:
- Demand distribution (skewness, log-demand)
- Demand intermittency (zero demand proportions, Croston / Syntetos-Boylan classification)
- SKU velocity Pareto analysis (ABC analysis)
- Temporal trends and seasonality (weekly volume, holiday surges)
- Geographic breakdown
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from src.config import FIGURES_DIR, TABLES_DIR, logger

# Set aesthetic style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8


def run_eda_pipeline(df_raw, df_cleaned, panel_df):
    """
    Run full EDA pipeline and generate all publication-grade figures and summary tables.
    """
    logger.info("=" * 60)
    logger.info("RUNNING COMPREHENSIVE EDA PIPELINE")
    logger.info("=" * 60)
    
    # 1. Geographic / Country breakdown
    logger.info("Generating Geographic Distribution...")
    country_counts = df_raw["Country"].value_counts().head(10)
    country_df = pd.DataFrame({
        "Country": country_counts.index,
        "Transactions": country_counts.values,
        "Percentage": (country_counts.values / len(df_raw)) * 100
    })
    country_df.to_csv(TABLES_DIR / "eda_country_distribution.csv", index=False)
    
    plt.figure(figsize=(9, 5))
    sns.barplot(data=country_df, x="Percentage", y="Country", palette="Blues_r")
    plt.title("Top 10 Countries by Transaction Share (%)", fontsize=13, pad=12)
    plt.xlabel("Share of Total Transactions (%)", fontsize=11)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "eda_country_distribution.png", dpi=300)
    plt.close()
    
    # 2. Demand Distribution (Raw vs Log1p)
    logger.info("Generating Demand Distribution Plots...")
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    # Clip extreme tail for visibility
    clip_val = np.percentile(panel_df["demand"], 99)
    sns.histplot(panel_df["demand"][panel_df["demand"] <= clip_val], bins=40, kde=True, color="#2b5c8f")
    plt.title(f"Weekly SKU Demand Distribution (clipped at 99th pct: {clip_val:.0f})", fontsize=11)
    plt.xlabel("Demand (Units)", fontsize=10)
    plt.ylabel("Frequency", fontsize=10)
    
    plt.subplot(1, 2, 2)
    sns.histplot(np.log1p(panel_df["demand"]), bins=40, kde=True, color="#d95f02")
    plt.title("Log-Transformed Demand Distribution: log(1 + Demand)", fontsize=11)
    plt.xlabel("log(1 + Demand)", fontsize=10)
    plt.ylabel("Frequency", fontsize=10)
    
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "eda_demand_distribution.png", dpi=300)
    plt.close()
    
    # 3. Time Series aggregate demand trend
    logger.info("Generating Aggregate Weekly Demand Trend...")
    weekly_agg = panel_df.groupby("week_start").agg(
        total_demand=("demand", "sum"),
        active_skus=("sku_id", "nunique"),
        avg_demand=("demand", "mean")
    ).reset_index()
    
    plt.figure(figsize=(12, 5))
    plt.plot(weekly_agg["week_start"], weekly_agg["total_demand"], color="#1f77b4", lw=2, label="Total Weekly Demand")
    plt.axvspan(pd.to_datetime("2010-11-01"), pd.to_datetime("2010-12-31"), color="orange", alpha=0.2, label="Q4 Holiday Surge (2010)")
    plt.axvspan(pd.to_datetime("2011-11-01"), pd.to_datetime("2011-12-31"), color="orange", alpha=0.2, label="Q4 Holiday Surge (2011)")
    plt.title("Total Weekly Retail Demand (2009 - 2011)", fontsize=13, pad=12)
    plt.xlabel("Date", fontsize=11)
    plt.ylabel("Total Units Demanded", fontsize=11)
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "eda_weekly_trend.png", dpi=300)
    plt.close()
    
    # 4. ABC Classification (Pareto Analysis)
    logger.info("Generating ABC Pareto Analysis...")
    sku_demand = panel_df.groupby("sku_id")["demand"].sum().sort_values(ascending=False).reset_index()
    sku_demand["cum_demand"] = sku_demand["demand"].cumsum()
    total_vol = sku_demand["demand"].sum()
    sku_demand["cum_pct"] = (sku_demand["cum_demand"] / total_vol) * 100
    sku_demand["sku_pct"] = ((sku_demand.index + 1) / len(sku_demand)) * 100
    
    # Assign ABC classes
    # Class A: top 80% volume (~20% SKUs)
    # Class B: next 15% volume (~30% SKUs)
    # Class C: remaining 5% volume (~50% SKUs)
    def assign_abc(pct):
        if pct <= 80:
            return "Class A (Top 80% Volume)"
        elif pct <= 95:
            return "Class B (Next 15% Volume)"
        else:
            return "Class C (Tail 5% Volume)"
            
    sku_demand["ABC_Class"] = sku_demand["cum_pct"].apply(assign_abc)
    abc_counts = sku_demand["ABC_Class"].value_counts().reset_index()
    abc_counts.columns = ["ABC_Class", "SKU_Count"]
    abc_counts["SKU_Share_Pct"] = (abc_counts["SKU_Count"] / len(sku_demand)) * 100
    abc_counts.to_csv(TABLES_DIR / "eda_abc_classification.csv", index=False)
    
    plt.figure(figsize=(8, 5))
    plt.plot(sku_demand["sku_pct"], sku_demand["cum_pct"], color="#2ca02c", lw=2.5)
    plt.plot([0, 100], [0, 100], color="gray", linestyle="--", alpha=0.7)
    plt.axhline(80, color="red", linestyle=":", label="80% Volume Cutoff (Class A)")
    plt.axhline(95, color="orange", linestyle=":", label="95% Volume Cutoff (Class B)")
    plt.title("Pareto Curve: Cumulative Demand vs SKU Share", fontsize=13)
    plt.xlabel("Cumulative SKU Share (%)", fontsize=11)
    plt.ylabel("Cumulative Demand (%)", fontsize=11)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "eda_abc_pareto.png", dpi=300)
    plt.close()
    
    # 5. Syntetos-Boylan Intermittency Categorization (ADI vs CV²)
    logger.info("Generating Demand Intermittency Classification (SBC)...")
    sku_intermittency = panel_df.groupby("sku_id").apply(
        lambda g: pd.Series({
            "adi": len(g) / max(1, (g["demand"] > 0).sum()),  # Average Demand Interval
            "cv2": (g[g["demand"] > 0]["demand"].std() / max(1e-6, g[g["demand"] > 0]["demand"].mean())) ** 2 if (g["demand"] > 0).sum() > 1 else 0.0
        })
    ).reset_index()
    
    # SBC Quadrants: ADI cutoff = 1.32, CV^2 cutoff = 0.49
    def sbc_classify(row):
        adi = row["adi"]
        cv2 = row["cv2"]
        if adi < 1.32 and cv2 < 0.49:
            return "Smooth"
        elif adi >= 1.32 and cv2 < 0.49:
            return "Intermittent"
        elif adi < 1.32 and cv2 >= 0.49:
            return "Erratic"
        else:
            return "Lumpy"
            
    sku_intermittency["Category"] = sku_intermittency.apply(sbc_classify, axis=1)
    sbc_summary = sku_intermittency["Category"].value_counts().reset_index()
    sbc_summary.columns = ["Demand_Type", "SKU_Count"]
    sbc_summary["Percentage"] = (sbc_summary["SKU_Count"] / len(sku_intermittency)) * 100
    sbc_summary.to_csv(TABLES_DIR / "eda_intermittency_sbc.csv", index=False)
    
    plt.figure(figsize=(7, 5))
    sns.countplot(data=sku_intermittency, x="Category", palette="Set2",
                  order=["Smooth", "Erratic", "Intermittent", "Lumpy"])
    plt.title("Syntetos-Boylan Demand Classification (SBC)", fontsize=13)
    plt.xlabel("Demand Pattern Category", fontsize=11)
    plt.ylabel("Number of SKUs", fontsize=11)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "eda_intermittency_sbc.png", dpi=300)
    plt.close()
    
    logger.info("EDA completed successfully! Figures and tables saved.")
