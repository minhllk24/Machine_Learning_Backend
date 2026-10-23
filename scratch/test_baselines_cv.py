import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

t0 = time.time()
print("Loading datasets...")
features_path = Path("data/processed/sku_week_features_v1_2_dev.parquet")
split_path = Path("data/processed/train_val_test_split_v1_1.json")
demand_path = Path("data/processed/sku_week_demand_v1_1.csv")

feat_df = pd.read_parquet(features_path)
split_info = json.loads(split_path.read_text(encoding="utf-8"))
demand_df = pd.read_csv(demand_path, low_memory=False)

print(f"Loaded features: {feat_df.shape}, demand: {demand_df.shape} in {time.time() - t0:.2f}s")

# Let's inspect unique SKUs and weeks
print(f"Total features SKUs: {feat_df['sku_id'].nunique()}, Target weeks: {feat_df['target_week'].nunique()}")
print(f"Min target week: {feat_df['target_week'].min()}, Max: {feat_df['target_week'].max()}")
