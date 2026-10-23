import mysql.connector
from mysql.connector import pooling
import pandas as pd
from typing import List, Dict, Any, Optional
from app.config import settings

# Khởi tạo Connection Pool tái sử dụng kết nối
db_pool = None

def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="retail_pool",
            pool_size=10,
            pool_reset_session=True,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME
        )
    return db_pool

def get_connection():
    """Lấy connection từ pool"""
    pool = get_db_pool()
    return pool.get_connection()

def query_dataframe(sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Thực thi câu lệnh SQL và trả về pandas DataFrame (Dành cho xử lý Machine Learning)"""
    conn = get_connection()
    try:
        if params:
            df = pd.read_sql(sql, conn, params=params)
        else:
            df = pd.read_sql(sql, conn)
        return df
    finally:
        conn.close()

def query_dict(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Thực thi câu lệnh SQL và trả về danh sách Dictionary (Dành cho REST API JSON)"""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        result = cursor.fetchall()
        cursor.close()
        return result
    finally:
        conn.close()

def execute_statement(sql: str, params: Optional[tuple] = None) -> int:
    """Thực thi UPDATE / INSERT / DELETE và trả về số dòng bị tác động"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        return affected
    finally:
        conn.close()
