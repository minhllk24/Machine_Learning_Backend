"""
Script xuat cau truc DDL schema va du lieu mau ra file .sql doc lap.
Phuc vu viec nop kem ma nguon do an hoac chia se cho thanh vien nhom import vao MySQL Workbench.
"""
import os
import sys
from pathlib import Path
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SQL_FILE = OUTPUT_DIR / "online_retail_db_dump.sql"

DDL_HEADER = """-- =====================================================================
-- RELATIONAL DATABASE DUMP: RETAIL DEMAND FORECASTING & INVENTORY PLANNING
-- Course: Machine Learning in Business Analytics (K24 - UEL)
-- Student: Le Minh (minhllk24)
-- Dialect: MySQL 8.0+ / MariaDB 10.4+ Compatible
-- Generated automatically for Deliverable 2 submission
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `online_retail_db`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `online_retail_db`;

-- Drop existing tables if needed for clean re-import
DROP TABLE IF EXISTS `forecast_inventory_decisions`;
DROP TABLE IF EXISTS `forecast_predictions`;
DROP TABLE IF EXISTS `sku_week_demand`;
DROP TABLE IF EXISTS `transactions`;

-- ---------------------------------------------------------------------
-- Table 1: transactions (Cleaned Transactions)
-- ---------------------------------------------------------------------
CREATE TABLE `transactions` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `invoice` VARCHAR(20) NOT NULL,
    `stock_code` VARCHAR(30) NOT NULL,
    `description` VARCHAR(255),
    `quantity` INT NOT NULL DEFAULT 0,
    `invoice_date` DATETIME NOT NULL,
    `price` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
    `customer_id` VARCHAR(20),
    `country` VARCHAR(50),
    `revenue` DECIMAL(12, 4) NOT NULL DEFAULT 0.0000,
    INDEX `idx_txn_stock_date` (`stock_code`, `invoice_date`),
    INDEX `idx_txn_inv` (`invoice`),
    INDEX `idx_txn_date` (`invoice_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 2: sku_week_demand (Weekly SKU Demand Panel)
-- ---------------------------------------------------------------------
CREATE TABLE `sku_week_demand` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `sku_id` VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `week_start` DATE NOT NULL,
    `demand` INT NOT NULL DEFAULT 0,
    `avg_unit_price` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
    `transaction_count` INT NOT NULL DEFAULT 0,
    `unique_customer_count` INT NOT NULL DEFAULT 0,
    `total_revenue` DECIMAL(12, 4) NOT NULL DEFAULT 0.0000,
    `min_price` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
    `max_price` DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,
    `zero_demand_flag` TINYINT NOT NULL DEFAULT 0,
    `is_active` TINYINT NOT NULL DEFAULT 1,
    INDEX `idx_panel_sku_week` (`sku_id`, `week_start`),
    INDEX `idx_panel_week` (`week_start`),
    INDEX `idx_panel_sku` (`sku_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 3: forecast_predictions (Holdout Model Predictions)
-- ---------------------------------------------------------------------
CREATE TABLE `forecast_predictions` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `model_id` VARCHAR(50) NOT NULL,
    `model_version` VARCHAR(20) NOT NULL,
    `cohort` VARCHAR(30),
    `sku_id` VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `forecast_origin` DATE NOT NULL,
    `target_week` DATE NOT NULL,
    `horizon_step` INT NOT NULL,
    `prediction_strategy` VARCHAR(30),
    `prediction_raw` DECIMAL(10, 4),
    `prediction` DECIMAL(10, 2) NOT NULL,
    `clipped_at_zero` TINYINT NOT NULL DEFAULT 0,
    `prediction_status` VARCHAR(20),
    `feature_schema_version` VARCHAR(20),
    `training_cutoff` DATE,
    INDEX `idx_pred_sku_week` (`sku_id`, `target_week`),
    INDEX `idx_pred_model` (`model_id`, `horizon_step`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 4: forecast_inventory_decisions (Replenishment Flags & Decisions)
-- ---------------------------------------------------------------------
CREATE TABLE `forecast_inventory_decisions` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `sku_id` VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    `forecast_week_start` DATE NOT NULL,
    `actual_demand` INT DEFAULT 0,
    `predicted_demand_lgbm` DECIMAL(10, 2) DEFAULT 0.00,
    `predicted_demand_catboost` DECIMAL(10, 2) DEFAULT 0.00,
    `lower_bound_90` DECIMAL(10, 2) DEFAULT 0.00,
    `upper_bound_90` DECIMAL(10, 2) DEFAULT 0.00,
    `simulated_current_stock` INT DEFAULT 0,
    `safety_buffer` DECIMAL(10, 2) DEFAULT 0.00,
    `projected_requirement` DECIMAL(10, 2) DEFAULT 0.00,
    `attention_flag` VARCHAR(30) DEFAULT 'ADEQUATE',
    `suggested_order_qty` INT DEFAULT 0,
    `created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_inv_sku_week` (`sku_id`, `forecast_week_start`),
    INDEX `idx_inv_flag` (`attention_flag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- SAMPLE DATA INSERTION (First 50 records per table for instant verification)
-- =====================================================================
"""

def generate_sample_inserts():
    inserts = []
    
    # 1. Transactions Sample
    txn_path = PROJECT_ROOT / "data" / "interim" / "cleaned_transactions.parquet"
    if txn_path.exists():
        df = pd.read_parquet(txn_path).head(50)
        inserts.append("\n-- Sample data for transactions (50 rows)")
        inserts.append("INSERT INTO `transactions` (`invoice`, `stock_code`, `description`, `quantity`, `invoice_date`, `price`, `customer_id`, `country`, `revenue`) VALUES")
        row_strs = []
        for row in df.itertuples(index=False):
            inv = str(row[0]).replace("'", "''")
            stock = str(row[1]).replace("'", "''")
            desc = str(row[2]).replace("'", "''") if pd.notna(row[2]) else ""
            qty = int(row[3]) if pd.notna(row[3]) else 0
            dt = str(row[4])[:19]
            pr = float(row[5]) if pd.notna(row[5]) else 0.0
            cust = str(int(row[6])) if pd.notna(row[6]) and str(row[6]).replace('.','').isdigit() else "NULL"
            cust_val = f"'{cust}'" if cust != "NULL" else "NULL"
            country = str(row[7]).replace("'", "''") if pd.notna(row[7]) else ""
            rev = float(row[8]) if pd.notna(row[8]) else (qty * pr)
            row_strs.append(f"('{inv}', '{stock}', '{desc}', {qty}, '{dt}', {pr:.4f}, {cust_val}, '{country}', {rev:.4f})")
        inserts.append(",\n".join(row_strs) + ";\n")

    # 2. Panel Sample
    panel_path = PROJECT_ROOT / "data" / "processed" / "sku_week_demand.csv"
    if panel_path.exists():
        df = pd.read_csv(panel_path, nrows=50)
        inserts.append("\n-- Sample data for sku_week_demand (50 rows)")
        inserts.append("INSERT INTO `sku_week_demand` (`sku_id`, `week_start`, `demand`, `avg_unit_price`, `transaction_count`, `unique_customer_count`, `total_revenue`, `min_price`, `max_price`, `zero_demand_flag`, `is_active`) VALUES")
        row_strs = []
        for row in df.itertuples(index=False):
            sku = str(row[0]).replace("'", "''")
            wk = str(row[1])[:10]
            dem = int(row[2]) if pd.notna(row[2]) else 0
            avg_p = float(row[3]) if pd.notna(row[3]) else 0.0
            cnt = int(row[4]) if pd.notna(row[4]) else 0
            cust = int(row[5]) if pd.notna(row[5]) else 0
            rev = float(row[6]) if pd.notna(row[6]) else 0.0
            min_p = float(row[7]) if pd.notna(row[7]) else 0.0
            max_p = float(row[8]) if pd.notna(row[8]) else 0.0
            zf = int(row[9]) if pd.notna(row[9]) else 0
            act = int(row[10]) if pd.notna(row[10]) else 1
            row_strs.append(f"('{sku}', '{wk}', {dem}, {avg_p:.4f}, {cnt}, {cust}, {rev:.4f}, {min_p:.4f}, {max_p:.4f}, {zf}, {act})")
        inserts.append(",\n".join(row_strs) + ";\n")

    return "\n".join(inserts)

def main():
    print("=" * 70)
    print("📦 XUAT TEP DDL SCHEMA VA DU LIEU MAU CHO MYSQL WORKBENCH")
    print("=" * 70)
    print(f"[*] Dang tao file: {SQL_FILE}")
    sample_sql = generate_sample_inserts()
    
    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write(DDL_HEADER)
        f.write(sample_sql)
        f.write("\n-- End of Dump\n")
        
    print(f"✅ [THANH CONG] File SQL da duoc xuat tai: {SQL_FILE}")
    print(f"   Dung luong: {SQL_FILE.stat().st_size / 1024:.1f} KB")
    print("   Thanh vien nhom co the mo file nay trong MySQL Workbench va chay (Execute) ngay!")
    print("=" * 70)

if __name__ == "__main__":
    main()

