"""
Script nạp toàn bộ dữ liệu vào MySQL cho đồ án Machine Learning Demand Forecasting:
1. Table `online_retail`: Dữ liệu thô từ online_retail_II.xlsx (1,067,371 dòng - ĐÃ NẠP)
2. Table `transactions`: Dữ liệu giao dịch đã làm sạch từ cleaned_transactions.parquet (1,003,466 dòng - ĐÃ NẠP)
3. Table `sku_week_demand`: Bảng panel nhu cầu theo tuần từ sku_week_demand.csv (288,560 dòng)
4. Table `forecast_predictions`: Kết quả dự báo mô hình từ test_predictions_phase8.parquet (111,400 dòng)
"""
import os
import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
import mysql.connector

# UTF-8 encoding support
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DATABASE', 'online_retail_db'),
    'autocommit': False
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def populate_transactions(batch_size=10000):
    parquet_path = PROJECT_ROOT / "data" / "interim" / "cleaned_transactions.parquet"
    if not parquet_path.exists():
        print(f"[!] Không tìm thấy file: {parquet_path}")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions;")
    cnt = cursor.fetchone()[0]
    
    if cnt >= 1003466:
        print(f"\n[1/3] Bảng 'transactions' ĐÃ ĐƯỢC NẠP ĐẦY ĐỦ: {cnt:,} dòng. Bỏ qua.")
        cursor.close()
        conn.close()
        return

    print(f"\n[1/3] Đang nạp bảng 'transactions' từ {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)
    total_rows = len(df)
    print(f"      Tổng số dòng cần nạp: {total_rows:,}")

    cursor.execute("SET autocommit = 0;")
    cursor.execute("SET unique_checks = 0;")
    cursor.execute("SET foreign_key_checks = 0;")
    cursor.execute("TRUNCATE TABLE transactions;")
    conn.commit()

    insert_sql = """
    INSERT INTO transactions (
        invoice, stock_code, description, quantity, invoice_date, price, customer_id, country, revenue
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    start = time.time()
    batch = []
    inserted = 0

    for row in df.itertuples(index=False):
        inv = str(row[0]).strip()
        stock = str(row[1]).strip()
        desc = str(row[2])[:255] if pd.notna(row[2]) else None
        qty = int(row[3]) if pd.notna(row[3]) else 0
        inv_date = row[4].to_pydatetime() if hasattr(row[4], 'to_pydatetime') else str(row[4])
        price = float(row[5]) if pd.notna(row[5]) else 0.0
        cust_id = str(int(row[6])) if pd.notna(row[6]) and str(row[6]).replace('.','').isdigit() else (str(row[6]) if pd.notna(row[6]) else None)
        country = str(row[7])[:50] if pd.notna(row[7]) else None
        rev = float(row[8]) if pd.notna(row[8]) else (qty * price)

        batch.append((inv, stock, desc, qty, inv_date, price, cust_id, country, rev))

        if len(batch) >= batch_size:
            cursor.executemany(insert_sql, batch)
            conn.commit()
            inserted += len(batch)
            batch.clear()

    if batch:
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)

    cursor.execute("SET unique_checks = 1;")
    cursor.execute("SET foreign_key_checks = 1;")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"      [+] Hoàn tất bảng 'transactions': {inserted:,} dòng ({time.time() - start:.1f}s).")

def populate_sku_week_demand(batch_size=10000):
    csv_path = PROJECT_ROOT / "data" / "processed" / "sku_week_demand.csv"
    if not csv_path.exists():
        print(f"[!] Không tìm thấy file: {csv_path}")
        return

    print(f"\n[2/3] Đang nạp bảng 'sku_week_demand' từ {csv_path.name}...")
    df = pd.read_csv(csv_path, low_memory=False)
    total_rows = len(df)
    print(f"      Tổng số dòng cần nạp: {total_rows:,}")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SET autocommit = 0;")
    cursor.execute("SET unique_checks = 0;")
    cursor.execute("SET foreign_key_checks = 0;")

    cursor.execute("TRUNCATE TABLE sku_week_demand;")
    conn.commit()

    insert_sql = """
    INSERT INTO sku_week_demand (
        sku_id, week_start, demand, avg_unit_price, transaction_count, 
        unique_customer_count, total_revenue, min_price, max_price, zero_demand_flag, is_active
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    start = time.time()
    batch = []
    inserted = 0

    for row in df.itertuples(index=False):
        sku_id = str(row[0]).strip()
        week_start = str(row[1])[:10]
        demand = int(row[2]) if pd.notna(row[2]) else 0
        avg_price = float(row[3]) if pd.notna(row[3]) else 0.0
        txn_cnt = int(row[4]) if pd.notna(row[4]) else 0
        cust_cnt = int(row[5]) if pd.notna(row[5]) else 0
        tot_rev = float(row[6]) if pd.notna(row[6]) else 0.0
        min_p = float(row[7]) if pd.notna(row[7]) else 0.0
        max_p = float(row[8]) if pd.notna(row[8]) else 0.0
        zero_flag = int(row[9]) if pd.notna(row[9]) else 0
        active = int(row[10]) if pd.notna(row[10]) else 1

        batch.append((sku_id, week_start, demand, avg_price, txn_cnt, cust_cnt, tot_rev, min_p, max_p, zero_flag, active))

        if len(batch) >= batch_size:
            cursor.executemany(insert_sql, batch)
            conn.commit()
            inserted += len(batch)
            batch.clear()
            elapsed = time.time() - start
            rate = inserted / elapsed if elapsed > 0 else 0
            print(f"      -> Đã nạp {inserted:,} / {total_rows:,} ({rate:,.0f} dòng/s)...")

    if batch:
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)

    cursor.execute("SET unique_checks = 1;")
    cursor.execute("SET foreign_key_checks = 1;")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"      [+] Hoàn tất bảng 'sku_week_demand': {inserted:,} dòng ({time.time() - start:.1f}s).")

def populate_forecast_predictions(batch_size=10000):
    parquet_path = PROJECT_ROOT / "data" / "processed" / "test_predictions_phase8.parquet"
    if not parquet_path.exists():
        print(f"[!] Không tìm thấy file: {parquet_path}")
        return

    print(f"\n[3/3] Đang nạp bảng 'forecast_predictions' từ {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)
    total_rows = len(df)
    print(f"      Tổng số dòng cần nạp: {total_rows:,}")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SET autocommit = 0;")
    cursor.execute("SET unique_checks = 0;")
    cursor.execute("SET foreign_key_checks = 0;")

    cursor.execute("TRUNCATE TABLE forecast_predictions;")
    conn.commit()

    insert_sql = """
    INSERT INTO forecast_predictions (
        model_id, model_version, cohort, sku_id, forecast_origin, target_week, 
        horizon_step, prediction_strategy, prediction_raw, prediction, 
        clipped_at_zero, prediction_status, feature_schema_version, training_cutoff
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    start = time.time()
    batch = []
    inserted = 0

    for row in df.itertuples(index=False):
        model_id = str(row[0])
        model_ver = str(row[1])
        cohort = str(row[2]) if pd.notna(row[2]) else None
        sku_id = str(row[3]).strip()
        origin = str(row[4])[:10] if pd.notna(row[4]) else None
        target = str(row[5])[:10] if pd.notna(row[5]) else None
        h_step = int(row[6]) if pd.notna(row[6]) else 1
        strat = str(row[7]) if pd.notna(row[7]) else None
        pred_raw = float(row[8]) if pd.notna(row[8]) else 0.0
        pred = float(row[9]) if pd.notna(row[9]) else 0.0
        clipped = int(row[10]) if pd.notna(row[10]) else 0
        status = str(row[11]) if pd.notna(row[11]) else 'OK'
        schema_ver = str(row[12]) if pd.notna(row[12]) else None
        cutoff = str(row[13])[:10] if pd.notna(row[13]) else None

        batch.append((model_id, model_ver, cohort, sku_id, origin, target, h_step, strat, pred_raw, pred, clipped, status, schema_ver, cutoff))

        if len(batch) >= batch_size:
            cursor.executemany(insert_sql, batch)
            conn.commit()
            inserted += len(batch)
            batch.clear()
            elapsed = time.time() - start
            rate = inserted / elapsed if elapsed > 0 else 0
            print(f"      -> Đã nạp {inserted:,} / {total_rows:,} ({rate:,.0f} dòng/s)...")

    if batch:
        cursor.executemany(insert_sql, batch)
        conn.commit()
        inserted += len(batch)

    cursor.execute("SET unique_checks = 1;")
    cursor.execute("SET foreign_key_checks = 1;")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"      [+] Hoàn tất bảng 'forecast_predictions': {inserted:,} dòng ({time.time() - start:.1f}s).")

def verify_all_tables():
    conn = get_connection()
    cursor = conn.cursor()
    print("\n" + "=" * 65)
    print(" BẢNG TỔNG HỢP KIỂM TRA DỮ LIỆU ĐÃ GẮN VÀO MYSQL (online_retail_db)")
    print("=" * 65)
    
    tables = [
        ("online_retail", "Dữ liệu thô từ Excel (2 sheet gộp lại)"),
        ("transactions", "Dữ liệu giao dịch đã làm sạch (Cleaned Transactions)"),
        ("sku_week_demand", "Bảng Panel nhu cầu theo tuần (Weekly SKU Demand)"),
        ("forecast_predictions", "Kết quả dự báo mô hình Machine Learning")
    ]
    
    for tbl, desc in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
            count = cursor.fetchone()[0]
            print(f"  * Bảng `{tbl}`: {count:,} dòng  ({desc})")
        except Exception as e:
            print(f"  * Bảng `{tbl}`: LỖI ({e})")
            
    cursor.close()
    conn.close()
    print("=" * 65)

if __name__ == '__main__':
    t_start = time.time()
    populate_transactions()
    populate_sku_week_demand()
    populate_forecast_predictions()
    verify_all_tables()
    print(f"\n[DONE] Hoàn tất toàn bộ quy trình gắn data vào MySQL trong {time.time() - t_start:.1f} giây!")
