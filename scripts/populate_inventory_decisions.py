"""
Populate MySQL Table 5: forecast_inventory_decisions.
Computes inventory replenishment metrics and attention flags (SHORTAGE RISK, ADEQUATE, EXCESS STOCK)
using holdout ML predictions and actual demand.
"""
import os
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import mysql.connector

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_connection():
    """Tạo kết nối tới MySQL Server dựa trên biến môi trường."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "123456"),
        database=os.getenv("MYSQL_DATABASE", "online_retail_db"),
        autocommit=False
    )

def ensure_schema_collated(conn):
    """Đảm bảo bảng forecast_inventory_decisions có cấu trúc chuẩn và sku_id COLLATE utf8mb4_bin."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_inventory_decisions (
        sku_id VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        forecast_week_start DATE NOT NULL,
        actual_demand INT DEFAULT 0,
        predicted_demand_lgbm DECIMAL(10, 2) DEFAULT 0.00,
        predicted_demand_catboost DECIMAL(10, 2) DEFAULT 0.00,
        lower_bound_90 DECIMAL(10, 2) DEFAULT 0.00,
        upper_bound_90 DECIMAL(10, 2) DEFAULT 0.00,
        simulated_current_stock INT DEFAULT 0,
        safety_buffer DECIMAL(10, 2) DEFAULT 0.00,
        projected_requirement DECIMAL(10, 2) DEFAULT 0.00,
        attention_flag VARCHAR(30) DEFAULT 'ADEQUATE',
        suggested_order_qty INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (sku_id, forecast_week_start),
        KEY idx_forecast_flag (attention_flag)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)
    conn.commit()

    # Đảm bảo cột sku_id dùng utf8mb4_bin để phân biệt hoa thường tránh lỗi trùng khóa
    try:
        cursor.execute("ALTER TABLE forecast_inventory_decisions MODIFY sku_id VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;")
        conn.commit()
    except Exception as e:
        print(f"[!] Ghi chú khi cập nhật collation: {e}")
    cursor.close()

def populate_inventory_decisions(batch_size=5000):
    pred_path = PROJECT_ROOT / "data" / "processed" / "test_predictions_phase8.parquet"
    demand_path = PROJECT_ROOT / "data" / "processed" / "sku_week_demand.csv"

    if not pred_path.exists() or not demand_path.exists():
        print(f"[!] Lỗi: Không tìm thấy file dữ liệu: {pred_path} hoặc {demand_path}")
        return 0

    print(f"\n[+] Đang xử lý dữ liệu tồn kho từ:")
    print(f"    * Dự báo: {pred_path.name}")
    print(f"    * Nhu cầu thực tế: {demand_path.name}")

    t0 = time.time()
    df_pred = pd.read_parquet(pred_path)
    df_demand = pd.read_csv(demand_path, low_memory=False)

    # Lọc mô hình CatBoost và Tweedie/Baseline
    cb_mae = df_pred[df_pred['model_id'] == 'CatBoost__MAE'][['sku_id', 'target_week', 'prediction']].rename(
        columns={'prediction': 'pred_catboost'}
    )
    cb_tw = df_pred[df_pred['model_id'] == 'CatBoost__Tweedie_p15'][['sku_id', 'target_week', 'prediction']].rename(
        columns={'prediction': 'pred_lgbm'}
    )

    merged = pd.merge(cb_mae, cb_tw, on=['sku_id', 'target_week'], how='inner')
    merged['target_week'] = merged['target_week'].astype(str)
    merged['sku_id'] = merged['sku_id'].astype(str).str.strip()

    df_demand['week_start'] = df_demand['week_start'].astype(str)
    df_demand['sku_id'] = df_demand['sku_id'].astype(str).str.strip()

    merged = pd.merge(
        merged,
        df_demand[['sku_id', 'week_start', 'demand']],
        left_on=['sku_id', 'target_week'],
        right_on=['sku_id', 'week_start'],
        how='left'
    )
    merged['demand'] = merged['demand'].fillna(0).astype(int)

    # Tính toán sai số dự báo và độ lệch chuẩn theo SKU
    merged['err'] = (merged['pred_catboost'] - merged['demand']).abs()
    sku_std = merged.groupby('sku_id')['err'].std().fillna(merged['err'].std()).clip(lower=1.0)
    
    # z = 1.28 cho cycle service level 90%
    merged['safety_buffer'] = (sku_std[merged['sku_id']].values * 1.28).round(2)
    merged['lower_bound_90'] = np.maximum(0.0, (merged['pred_catboost'] - merged['safety_buffer'])).round(2)
    merged['upper_bound_90'] = (merged['pred_catboost'] + merged['safety_buffer']).round(2)
    merged['projected_requirement'] = (merged['pred_catboost'] + merged['safety_buffer']).round(2)

    # Mô phỏng tồn kho hiện tại (simulated_current_stock)
    np.random.seed(42)
    multipliers = np.random.choice([0.3, 0.7, 1.1, 1.5, 2.8], size=len(merged), p=[0.25, 0.25, 0.30, 0.10, 0.10])
    merged['simulated_current_stock'] = np.maximum(0, (multipliers * merged['projected_requirement']).round().astype(int))

    # Gán attention_flag theo chuẩn
    def assign_flag(row):
        if row['simulated_current_stock'] < row['safety_buffer']:
            return 'SHORTAGE RISK'
        elif row['simulated_current_stock'] > 2.5 * row['projected_requirement']:
            return 'EXCESS STOCK'
        else:
            return 'ADEQUATE'

    merged['attention_flag'] = merged.apply(assign_flag, axis=1)
    merged['suggested_order_qty'] = np.maximum(0, (merged['projected_requirement'] - merged['simulated_current_stock']).round().astype(int))

    total_rows = len(merged)
    print(f"    * Tổng số quyết định tồn kho đã tính toán: {total_rows:,} dòng ({time.time() - t0:.2f}s)")
    print(f"    * Phân phối trạng thái tồn kho:")
    for flag_name, count in merged['attention_flag'].value_counts().items():
        print(f"      - {flag_name:<15}: {count:,} ({count/total_rows*100:.1f}%)")

    conn = get_connection()
    ensure_schema_collated(conn)
    cursor = conn.cursor()

    cursor.execute("SET autocommit = 0;")
    cursor.execute("SET unique_checks = 0;")
    cursor.execute("SET foreign_key_checks = 0;")

    cursor.execute("TRUNCATE TABLE forecast_inventory_decisions;")
    conn.commit()

    insert_sql = """
    INSERT INTO forecast_inventory_decisions (
        sku_id, forecast_week_start, actual_demand,
        predicted_demand_lgbm, predicted_demand_catboost,
        lower_bound_90, upper_bound_90,
        simulated_current_stock, safety_buffer, projected_requirement,
        attention_flag, suggested_order_qty
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    start_insert = time.time()
    batch = []
    inserted = 0

    for row in merged.itertuples(index=False):
        batch.append((
            str(row.sku_id),
            str(row.target_week)[:10],
            int(row.demand),
            float(row.pred_lgbm),
            float(row.pred_catboost),
            float(row.lower_bound_90),
            float(row.upper_bound_90),
            int(row.simulated_current_stock),
            float(row.safety_buffer),
            float(row.projected_requirement),
            str(row.attention_flag),
            int(row.suggested_order_qty)
        ))

        if len(batch) >= batch_size:
            cursor.executemany(insert_sql, batch)
            conn.commit()
            inserted += len(batch)
            batch.clear()
            elapsed = time.time() - start_insert
            print(f"      -> Đã nạp {inserted:,} / {total_rows:,} ({inserted/elapsed:,.0f} dòng/s)...")

    if batch:
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)

    cursor.execute("SET unique_checks = 1;")
    cursor.execute("SET foreign_key_checks = 1;")
    conn.commit()

    cursor.close()
    conn.close()
    print(f"[+] Nạp thành công {inserted:,} dòng vào bảng 'forecast_inventory_decisions' trong {time.time() - start_insert:.2f}s!")
    return inserted

if __name__ == "__main__":
    populate_inventory_decisions()
