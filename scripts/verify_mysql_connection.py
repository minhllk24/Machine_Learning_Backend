"""
Script kiem tra suc khoe va tu dong chan doan ket noi MySQL Server.
Phuc vu Deliverable 2 - Do an Hoc may trong phan tich kinh doanh (UEL K24).
Nguoi thuc hien: Le Minh (minhllk24).
"""
import os
import sys
import socket
from pathlib import Path
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("MYSQL_PORT", 3306))
USER = os.getenv("MYSQL_USER", "root")
PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DATABASE = os.getenv("MYSQL_DATABASE", "online_retail_db")

def check_port(host: str, port: int, timeout=2.0) -> bool:
    """Kiem tra xem port MySQL co dang mo va lang nghe ket noi hay khong."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def main():
    print("=" * 70)
    print("🔍 KIEM TRA VA CHAN DOAN KET NOI MYSQL SERVER (DELIVERABLE 2)")
    print("=" * 70)
    print(f"[*] Thong so cau hinh tu file .env:")
    print(f"    - Host:     {HOST}")
    print(f"    - Port:     {PORT}")
    print(f"    - User:     {USER}")
    print(f"    - Database: {DATABASE}")
    print(f"    - Password: {'[configured]' if PASSWORD else '[empty]'}")
    print("-" * 70)

    # 1. Kiem tra Port
    print(f"[1/3] Kiem tra ket noi mang toi {HOST}:{PORT}...")
    if not check_port(HOST, PORT):
        print(f"❌ [THAT BAI] Khong the ket noi toi cong {PORT} tren host '{HOST}'!")
        print("\n👉 NGUYEN NHAN & HUONG KHAC PHUC:")
        print("   1. Dich vu MySQL Server chua duoc bat.")
        print("      -> Nhan to hop phim Win + R, go 'services.msc' va nhan Enter.")
        print("      -> Tim dich vu 'MySQL80' (hoac 'MySQL'), nhap chuot phai va chon 'Start'.")
        print("      -> Neu dung XAMPP, hay mo 'XAMPP Control Panel' va nhan nut 'Start' o dong MySQL.")
        print("   2. MySQL dang chay o mot cong khac (vi du: 3307 thay vi 3306).")
        print("      -> Kiem tra lai port trong MySQL Workbench va sua trong file .env.")
        print("=" * 70)
        return False

    print(f"✅ [THANH CONG] Cong {PORT} dang mo va san sang tiep nhan ket noi.")

    # 2. Kiem tra Thu vien & Thong tin Dang nhap (Auth)
    print(f"\n[2/3] Kiem tra xac thuc nguoi dung '{USER}'...")
    try:
        import mysql.connector
        from mysql.connector import errorcode
    except ImportError:
        print("❌ [LOI] Chua cai dat thu vien 'mysql-connector-python'!")
        print("   -> Chay lenh: .venv\\Scripts\\pip install mysql-connector-python")
        return False

    try:
        # Thu ket noi khong chi dinh database truoc (de check user/pass)
        conn = mysql.connector.connect(
            host=HOST,
            port=PORT,
            user=USER,
            password=PASSWORD,
            connection_timeout=5
        )
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        print(f"✅ [THANH CONG] Dang nhap hop le! Phien ban MySQL Server: {version}")
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print(f"❌ [THAT BAI] Sai User hoac Password MySQL! (Error code: {err.errno})")
            print("👉 HUONG KHAC PHUC:")
            print("   -> Mo file .env va chinh sua bien MYSQL_PASSWORD khop voi mat khau root cua ban.")
        else:
            print(f"❌ [LOI] {err}")
        return False

    # 3. Kiem tra Database & Cac Bang
    print(f"\n[3/3] Kiem tra Database '{DATABASE}' va cac bang du lieu...")
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE `{DATABASE}`;")
        cursor.execute("SHOW TABLES;")
        tables = [t[0] for t in cursor.fetchall()]

        if not tables:
            print(f"⚠️  Database '{DATABASE}' da ton tai nhung CHUA CO BANG DU LIEU.")
            print("👉 Buoc tiep theo: Chay script nap du lieu:")
            print("   .venv\\Scripts\\python scripts/populate_mysql_all.py")
        else:
            print(f"✅ Database '{DATABASE}' da co {len(tables)} bang:")
            total_records = 0
            for tbl in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                cnt = cursor.fetchone()[0]
                total_records += cnt
                print(f"   - {tbl:30s}: {cnt:>10,d} dong")
            print(f"   => Tong cong: {total_records:>10,d} ban ghi.")

        cursor.close()
        conn.close()
        print("\n" + "=" * 70)
        print("🎉 XAC NHAN: HE THONG MYSQL DA SAN SANG 100% PHUC VU DO AN!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"❌ [LOI] Khong the truy van database: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

