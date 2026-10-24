"""
End-to-End (E2E) Master Test Suite for Backend, MySQL, FastAPI, Vercel CORS, and Planning.
Verifies all 5 Master Work Packages for the Demand Forecasting Platform.
"""
import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.database import get_mysql_connection
from src.services.mysql_service import mysql_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# =====================================================================
# GÓI 1: KIỂM THỬ CSDL MYSQL VÀ BẢNG SỐ 5 (forecast_inventory_decisions)
# =====================================================================

def test_mysql_five_tables_data_integrity():
    """Xác thực toàn bộ 5 bảng dữ liệu trong MySQL đều tồn tại và có đầy đủ dữ liệu."""
    conn = get_mysql_connection()
    cursor = conn.cursor()

    expected_tables = {
        "online_retail": 1_000_000,
        "transactions": 1_000_000,
        "sku_week_demand": 280_000,
        "forecast_predictions": 110_000,
        "forecast_inventory_decisions": 20_000,
    }

    counts = {}
    for tbl, min_rows in expected_tables.items():
        cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
        cnt = cursor.fetchone()[0]
        counts[tbl] = cnt
        assert cnt >= min_rows, f"Bảng {tbl} có {cnt:,} dòng, kỳ vọng ít nhất {min_rows:,} dòng!"

    cursor.close()
    conn.close()

    assert counts["forecast_inventory_decisions"] == 22_280, (
        f"Bảng số 5 kỳ vọng đúng 22,280 dòng nhưng nhận được {counts['forecast_inventory_decisions']}"
    )


def test_inventory_decisions_flag_distribution():
    """Kiểm tra bảng số 5 có đủ 3 cờ trạng thái tồn kho chuẩn hóa."""
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT attention_flag, COUNT(*) FROM forecast_inventory_decisions GROUP BY attention_flag;")
    flag_counts = dict(cursor.fetchall())
    cursor.close()
    conn.close()

    assert "ADEQUATE" in flag_counts, "Thiếu trạng thái ADEQUATE trong bảng tồn kho"
    assert "SHORTAGE RISK" in flag_counts, "Thiếu trạng thái SHORTAGE RISK trong bảng tồn kho"
    assert "EXCESS STOCK" in flag_counts, "Thiếu trạng thái EXCESS STOCK trong bảng tồn kho"
    assert flag_counts["SHORTAGE RISK"] > 0
    assert flag_counts["ADEQUATE"] > 0
    assert flag_counts["EXCESS STOCK"] > 0


# =====================================================================
# GÓI 2: KIỂM THỬ FASTAPI DATA ACCESS LAYER & REST API ENDPOINTS
# =====================================================================

def test_database_health_endpoint(client: TestClient):
    """Kiểm tra endpoint /api/v1/database/health phản hồi 200 và thống kê chuẩn."""
    response = client.get("/api/v1/database/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["connected"] is True
    assert data["database_name"] == "online_retail_db"
    assert data["total_records"] >= 2_490_000
    assert "forecast_inventory_decisions" in data["tables"]


def test_database_transactions_pagination(client: TestClient):
    """Kiểm tra phân trang giao dịch qua /api/v1/database/transactions."""
    response = client.get("/api/v1/database/transactions?limit=15&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1_000_000
    assert data["limit"] == 15
    assert data["offset"] == 0
    assert len(data["items"]) == 15

    item = data["items"][0]
    assert "invoice" in item
    assert "stock_code" in item
    assert "quantity" in item
    assert "price" in item


def test_database_sku_demand_history(client: TestClient):
    """Kiểm tra chuỗi thời gian nhu cầu lịch sử /api/v1/database/demand-history/{sku_id}."""
    response = client.get("/api/v1/database/demand-history/10002?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "10002"
    assert data["points_count"] > 0
    assert len(data["history"]) <= 10

    hist_point = data["history"][0]
    assert "week_start" in hist_point
    assert "demand" in hist_point
    assert "total_revenue" in hist_point


def test_database_inventory_decisions_filtering(client: TestClient):
    """Kiểm tra bộ lọc theo attention_flag trên /api/v1/database/inventory-decisions."""
    # 1. Truy vấn không lọc
    res_all = client.get("/api/v1/database/inventory-decisions?limit=25")
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["total"] == 22_280
    assert "summary" in data_all
    assert len(data_all["items"]) == 25

    # 2. Truy vấn chỉ SHORTAGE RISK
    res_short = client.get("/api/v1/database/inventory-decisions?attention_flag=SHORTAGE%20RISK&limit=10")
    assert res_short.status_code == 200
    data_short = res_short.json()
    assert data_short["total"] == 7_746
    for item in data_short["items"]:
        assert item["attention_flag"] == "SHORTAGE RISK"
        assert item["suggested_order_qty"] >= 0


# =====================================================================
# GÓI 3: KIỂM THỬ BẢO MẬT & DYNAMIC CORS CHO VERCEL FRONTEND
# =====================================================================

def test_cors_vercel_preview_domain_allowed(client: TestClient):
    """Kiểm tra domain Vercel preview được phép gọi API Backend qua CORS."""
    origin = "https://retail-forecasting-preview-minh.vercel.app"
    response = client.get(
        "/health",
        headers={"Origin": origin}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_vercel_production_domain_allowed(client: TestClient):
    """Kiểm tra domain Vercel production chính thức được phép gọi API."""
    origin = "https://retail-forecast-frontend.vercel.app"
    response = client.get(
        "/api/v1/database/health",
        headers={"Origin": origin}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


# =====================================================================
# GÓI 4 & 5: KIỂM THỬ GRACEFUL DEGRADATION & DESKTOP PYQT6 DATA LAYER
# =====================================================================

def test_graceful_degradation_probe_fallback(monkeypatch):
    """Kiểm thử cơ chế Graceful Degradation: Không crash khi mất kết nối MySQL."""
    def fake_failing_connection():
        raise ConnectionRefusedError("Simulated MySQL Server Down")

    monkeypatch.setattr("src.services.mysql_service.get_mysql_connection", fake_failing_connection)

    health = mysql_service.get_database_health()
    assert health["status"] == "unavailable"
    assert health["connected"] is False
    assert "Simulated MySQL Server Down" in health["error"]
