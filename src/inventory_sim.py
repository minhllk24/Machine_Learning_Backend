"""
Inventory Planning Simulation Module.
Translates ML demand forecast accuracy (MAE/WAPE) into bottom-line retail business metrics:
- Service Level (Cycle Service Level & Fill Rate)
- Stockout Weeks & Lost Sales Units
- Inventory Holding Cost vs Stockout Penalty Cost
- Total Logistics & Inventory Cost
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from src.config import FIGURES_DIR, TABLES_DIR, logger


def simulate_inventory_policy(
    df_eval,
    pred_col="pred_lgbm",
    target_col="target",
    unit_holding_cost=0.5,     # Cost per unsold unit per week (e.g. £0.50)
    unit_stockout_cost=2.0,    # Lost gross margin per unfulfilled unit (e.g. £2.00)
    target_service_level=0.90, # 90% target cycle service level
):
    """
    Simulate weekly periodic review inventory replenishment for each SKU over time.
    
    Order Quantity Q_t:
        Target inventory = Forecast(t) + Safety Stock (SS)
        SS = z * std(forecast_error)
        Order = max(0, Target inventory - Beginning Inventory)
    """
    df = df_eval.copy().sort_values(["sku_id", "week_start"])
    
    # Calculate safety stock factor based on normal distribution approximation
    # z = 1.28 for 90%, 1.645 for 95%
    z_map = {0.80: 0.84, 0.85: 1.04, 0.90: 1.28, 0.95: 1.65, 0.99: 2.33}
    z = z_map.get(target_service_level, 1.28)
    
    # Forecast error standard deviation per SKU
    df["err"] = df[pred_col] - df[target_col]
    sku_err_std = df.groupby("sku_id")["err"].std().fillna(df["err"].std())
    df["safety_stock"] = df["sku_id"].map(sku_err_std) * z
    df["safety_stock"] = np.maximum(0.0, df["safety_stock"])
    
    total_demand = 0.0
    total_sales = 0.0
    total_lost_sales = 0.0
    total_holding_units = 0.0
    stockout_events = 0
    total_periods = len(df)
    
    # Fast vectorized simulation by SKU
    skus = df["sku_id"].unique()
    
    all_ending_inventory = []
    all_lost_sales = []
    
    for sku in skus:
        sku_data = df[df["sku_id"] == sku]
        inv = 0.0  # Initial inventory
        
        for _, row in sku_data.iterrows():
            demand = row[target_col]
            pred = row[pred_col]
            ss = row["safety_stock"]
            
            # Replenishment arrives: order up to pred + ss
            order = max(0.0, pred + ss - inv)
            available = inv + order
            
            if available >= demand:
                sales = demand
                lost = 0.0
                inv = available - demand
            else:
                sales = available
                lost = demand - available
                inv = 0.0
                stockout_events += 1
                
            total_demand += demand
            total_sales += sales
            total_lost_sales += lost
            total_holding_units += inv
            
    fill_rate = total_sales / (total_demand + 1e-6)
    cycle_service_level = 1.0 - (stockout_events / total_periods)
    holding_cost = total_holding_units * unit_holding_cost
    stockout_cost = total_lost_sales * unit_stockout_cost
    total_cost = holding_cost + stockout_cost
    
    return {
        "Model": pred_col,
        "Total_Demand": total_demand,
        "Satisfied_Sales": total_sales,
        "Lost_Sales_Units": total_lost_sales,
        "Fill_Rate": fill_rate,
        "Cycle_Service_Level": cycle_service_level,
        "Stockout_Rate": stockout_events / total_periods,
        "Holding_Cost": holding_cost,
        "Stockout_Cost": stockout_cost,
        "Total_Cost": total_cost,
    }


def compare_inventory_policies(df_eval, model_cols, target_col="target"):
    """
    Compare inventory policy performance across all models (Baselines vs ML).
    """
    results = []
    for col in model_cols:
        res = simulate_inventory_policy(df_eval, pred_col=col, target_col=target_col)
        res["Model"] = col
        results.append(res)
        
    res_df = pd.DataFrame(results)
    
    # Calculate savings compared to baseline
    baseline_cost = res_df.iloc[0]["Total_Cost"]
    res_df["Cost_Reduction_Pct"] = ((baseline_cost - res_df["Total_Cost"]) / baseline_cost) * 100
    res_df.to_csv(TABLES_DIR / "inventory_simulation_comparison.csv", index=False)
    
    logger.info("Inventory Policy Simulation Results:")
    for _, row in res_df.iterrows():
        logger.info(f"  [{row['Model']}]: Fill Rate={row['Fill_Rate']*100:.2f}%, Total Cost=£{row['Total_Cost']:,.2f} (Savings: {row['Cost_Reduction_Pct']:.1f}%)")
        
    return res_df
