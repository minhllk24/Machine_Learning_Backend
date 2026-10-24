"""
Database Module for Demand Forecasting & Inventory Planning.
Provides SQLite database integration and MySQL-compatible DDL schemas
to satisfy the relational database deliverable (Deliverable 2).
"""
import sqlite3
import pandas as pd
from pathlib import Path
from src.config import DATA_DIR, TABLES_DIR, logger

DB_PATH = DATA_DIR / "inventory_forecasting.db"
SQL_SCHEMA_PATH = TABLES_DIR / "schema.sql"

MYSQL_DDL = """-- ============================================================
-- RELATIONAL DATABASE SCHEMA: RETAIL DEMAND FORECASTING
-- Dialect: MySQL 8.0+ / SQLite3 compatible
-- ============================================================

-- Table 1: Raw / Cleaned Transactions
CREATE TABLE IF NOT EXISTS transactions (
    invoice VARCHAR(20) NOT NULL,
    stock_code VARCHAR(30) NOT NULL,
    description TEXT,
    quantity INT NOT NULL,
    invoice_date DATETIME NOT NULL,
    price DECIMAL(10, 4) NOT NULL,
    customer_id VARCHAR(20),
    country VARCHAR(50),
    revenue DECIMAL(12, 4),
    PRIMARY KEY (invoice, stock_code, invoice_date)
);

-- Indexing for fast time-series aggregation
CREATE INDEX IF NOT EXISTS idx_txn_stock_date ON transactions (stock_code, invoice_date);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions (invoice_date);

-- Table 2: Weekly SKU Demand Panel
CREATE TABLE IF NOT EXISTS sku_week_demand (
    sku_id VARCHAR(30) NOT NULL,
    week_start DATE NOT NULL,
    demand INT NOT NULL DEFAULT 0,
    avg_unit_price DECIMAL(10, 4),
    transaction_count INT NOT NULL DEFAULT 0,
    unique_customer_count INT NOT NULL DEFAULT 0,
    total_revenue DECIMAL(12, 4) DEFAULT 0.0,
    zero_demand_flag TINYINT NOT NULL DEFAULT 0,
    is_active TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (sku_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_panel_sku ON sku_week_demand (sku_id);
CREATE INDEX IF NOT EXISTS idx_panel_week ON sku_week_demand (week_start);

-- Table 3: Model Forecasts & Inventory Planning Attention Flags
CREATE TABLE IF NOT EXISTS forecast_inventory_decisions (
    sku_id VARCHAR(30) NOT NULL,
    forecast_week_start DATE NOT NULL,
    actual_demand INT,
    predicted_demand_lgbm DECIMAL(10, 2),
    predicted_demand_catboost DECIMAL(10, 2),
    lower_bound_90 DECIMAL(10, 2),
    upper_bound_90 DECIMAL(10, 2),
    simulated_current_stock INT,
    safety_buffer DECIMAL(10, 2),
    projected_requirement DECIMAL(10, 2),
    attention_flag VARCHAR(30), -- 'SHORTAGE RISK', 'ADEQUATE', 'EXCESS STOCK'
    suggested_order_qty INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sku_id, forecast_week_start)
);

CREATE INDEX IF NOT EXISTS idx_forecast_flag ON forecast_inventory_decisions (attention_flag);
"""


def export_mysql_schema():
    """Write DDL file to artifacts."""
    with open(SQL_SCHEMA_PATH, "w", encoding="utf-8") as f:
        f.write(MYSQL_DDL)
    logger.info(f"Exported MySQL/SQLite DDL schema to {SQL_SCHEMA_PATH}")


def populate_sqlite_db(df_cleaned=None, panel_df=None, test_predictions=None):
    """
    Populate SQLite database for relational queries and application integration.
    """
    logger.info(f"Connecting to SQLite database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(MYSQL_DDL)
    
    if panel_df is not None:
        logger.info(f"Writing {len(panel_df):,} rows to 'sku_week_demand'...")
        panel_df.to_sql("sku_week_demand", conn, if_exists="replace", index=False)
        
    if test_predictions is not None:
        logger.info(f"Writing {len(test_predictions):,} rows to 'forecast_inventory_decisions'...")
        test_predictions.to_sql("forecast_inventory_decisions", conn, if_exists="replace", index=False)
        
    conn.commit()
    conn.close()
    logger.info("SQLite database populated successfully.")


_mysql_pool = None


def get_mysql_pool():
    """Khởi tạo và trả về MySQLConnectionPool tái sử dụng kết nối."""
    global _mysql_pool
    if _mysql_pool is None:
        from mysql.connector import pooling
        from src.core.config import settings
        _mysql_pool = pooling.MySQLConnectionPool(
            pool_name="retail_pool",
            pool_size=settings.MYSQL_POOL_SIZE,
            pool_reset_session=True,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
        )
        logger.info(f"MySQL Connection Pool 'retail_pool' initialized (size={settings.MYSQL_POOL_SIZE}).")
    return _mysql_pool


def get_mysql_connection():
    """Lấy connection từ connection pool hoặc tạo kết nối trực tiếp nếu pool lỗi."""
    import mysql.connector
    from src.core.config import settings
    try:
        pool = get_mysql_pool()
        return pool.get_connection()
    except Exception as e:
        logger.warning(f"Connection pool unavailable ({e}), falling back to direct connection.")
        return mysql.connector.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            connection_timeout=3,
            autocommit=False
        )


def populate_mysql_db():
    """Nạp toàn bộ dữ liệu sạch, panel tuần, dự báo và tồn kho vào MySQL."""
    from scripts.populate_mysql_all import (
        populate_transactions,
        populate_sku_week_demand,
        populate_forecast_predictions,
        verify_all_tables
    )
    from scripts.populate_inventory_decisions import populate_inventory_decisions
    
    logger.info("Bắt đầu đồng bộ toàn bộ 5 bảng dữ liệu vào MySQL (online_retail_db)...")
    populate_transactions()
    populate_sku_week_demand()
    populate_forecast_predictions()
    populate_inventory_decisions()
    verify_all_tables()


if __name__ == "__main__":
    export_mysql_schema()
    populate_sqlite_db()
    populate_mysql_db()

