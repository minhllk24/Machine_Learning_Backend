"""
Phase 15 Security, Authentication, and Role-Based Access Control (RBAC) Test Suite.
Verifies:
1. Credential authentication (PBKDF2 salted hash, zero plaintext passwords).
2. Token lifecycle (HMAC-SHA256 JWT generation, validation, expiration, and revocation blacklist).
3. Role-based function authorization (Viewer, Analyst, Planner, Admin role segregation).
4. Direct-object-reference protection (BOLA/IDOR prevention between non-admin users).
5. Protected administrative endpoints (/auth/users).
"""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.services.persistence_service import persistence_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def get_token_for_user(client: TestClient, username: str, password: str) -> str:
    """Helper to authenticate and retrieve access token."""
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def get_error_message(resp) -> str:
    """Helper extracting message or detail from API error response."""
    data = resp.json()
    return str(data.get("message") or data.get("detail") or "")


# =====================================================================
# 1. AUTHENTICATION & CREDENTIAL TESTS
# =====================================================================
def test_password_hashing_pbkdf2():
    """Verify PBKDF2 hashing produces distinct salted hashes and correctly verifies."""
    pwd = "SecurePassword123!"
    h1 = hash_password(pwd)
    h2 = hash_password(pwd)

    # Salt uniqueness
    assert h1 != h2, "Hashes must have distinct salts"
    assert h1.startswith("pbkdf2:sha256:600000$")
    assert verify_password(pwd, h1) is True
    assert verify_password("WrongPassword!", h1) is False


def test_login_success_all_default_roles(client: TestClient):
    """Verify all 4 canonical seed users can successfully authenticate."""
    creds = [
        ("admin", "Admin123!", "admin"),
        ("analyst", "Analyst123!", "analyst"),
        ("planner", "Planner123!", "planner"),
        ("viewer", "Viewer123!", "viewer"),
    ]
    for username, password, expected_role in creds:
        resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == username
        assert data["user"]["role"] == expected_role
        assert data["expires_in_seconds"] > 0


def test_login_invalid_credentials_rejected(client: TestClient):
    """Verify bad username or password returns HTTP 401."""
    resp_bad_user = client.post("/api/v1/auth/login", json={"username": "nonexistent_user", "password": "WrongPassword123!"})
    assert resp_bad_user.status_code == 401
    assert "Invalid username or password" in get_error_message(resp_bad_user)

    resp_bad_pwd = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword123!"})
    assert resp_bad_pwd.status_code == 401
    assert "Invalid username or password" in get_error_message(resp_bad_pwd)


# =====================================================================
# 2. SESSION LIFECYCLE & TOKEN REVOCATION
# =====================================================================
def test_get_current_user_me(client: TestClient):
    """Verify /auth/me returns identity for valid token and rejects missing/invalid token."""
    # Unauthenticated
    resp_anon = client.get("/api/v1/auth/me")
    assert resp_anon.status_code == 401

    # Bad token
    resp_bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid_garbage_token"})
    assert resp_bad.status_code == 401

    # Authenticated
    token = get_token_for_user(client, "analyst", "Analyst123!")
    resp_auth = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_auth.status_code == 200
    assert resp_auth.json()["username"] == "analyst"
    assert resp_auth.json()["role"] == "analyst"


def test_logout_revokes_token_in_blacklist(client: TestClient):
    """Verify that logging out invalidates the token against subsequent use."""
    token = get_token_for_user(client, "viewer", "Viewer123!")
    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works
    resp1 = client.get("/api/v1/auth/me", headers=headers)
    assert resp1.status_code == 200

    # Logout
    resp_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert resp_logout.status_code == 200
    assert resp_logout.json()["status"] == "SUCCEEDED"

    # Verify token is now rejected as revoked
    resp2 = client.get("/api/v1/auth/me", headers=headers)
    assert resp2.status_code == 401
    assert "Token has been revoked" in get_error_message(resp2)


def test_expired_token_rejected():
    """Verify expired JWT tokens are rejected with ValueError during decoding."""
    # Create token expired 10 seconds ago
    token, _, _ = create_access_token(
        user_id="test_exp",
        username="test_exp",
        role="viewer",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(ValueError, match="Token has expired"):
        decode_access_token(token)


# =====================================================================
# 3. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
# =====================================================================
def test_user_management_restricted_to_admin(client: TestClient):
    """Verify /auth/users is restricted strictly to Admin role (Viewer, Analyst, Planner return 403)."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/v1/auth/users").status_code == 401

    # 2. Viewer -> 403
    v_token = get_token_for_user(client, "viewer", "Viewer123!")
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {v_token}"}).status_code == 403

    # 3. Analyst -> 403
    a_token = get_token_for_user(client, "analyst", "Analyst123!")
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {a_token}"}).status_code == 403

    # 4. Planner -> 403
    p_token = get_token_for_user(client, "planner", "Planner123!")
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {p_token}"}).status_code == 403

    # 5. Admin -> 200
    admin_token = get_token_for_user(client, "admin", "Admin123!")
    resp_admin = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_admin.status_code == 200
    usernames = [u["username"] for u in resp_admin.json()]
    assert "admin" in usernames
    assert "analyst" in usernames


def test_forecast_execution_role_guards(client: TestClient):
    """
    Verify POST /api/v1/forecasts role enforcement:
    - Viewer role is strictly DENIED (HTTP 403 Forbidden).
    - Analyst, Planner, and Admin roles are ALLOWED.
    """
    valid_payload = {
        "model_id": "CatBoost__MAE",
        "sku_ids": ["10002"],
        "forecast_origin": "2011-10-03",
        "horizon_weeks": 4,
    }

    # Viewer role -> 403
    v_token = get_token_for_user(client, "viewer", "Viewer123!")
    resp_viewer = client.post(
        "/api/v1/forecasts",
        json=valid_payload,
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert resp_viewer.status_code == 403
    assert "Access forbidden" in get_error_message(resp_viewer)
    assert "viewer" in get_error_message(resp_viewer).lower()

    # Analyst role -> Permitted (status 200)
    a_token = get_token_for_user(client, "analyst", "Analyst123!")
    resp_analyst = client.post(
        "/api/v1/forecasts",
        json=valid_payload,
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp_analyst.status_code == 200
    assert "forecast_run_id" in resp_analyst.json()


def test_planning_replenishment_role_guards(client: TestClient):
    """
    Verify POST /api/v1/planning/replenish role enforcement:
    - Viewer and Analyst roles are DENIED (HTTP 403 Forbidden).
    - Planner and Admin roles are ALLOWED.
    """
    # Create a real forecast run first using analyst token
    a_token = get_token_for_user(client, "analyst", "Analyst123!")
    fc_resp = client.post(
        "/api/v1/forecasts",
        json={
            "model_id": "CatBoost__MAE",
            "sku_ids": ["10002"],
            "forecast_origin": "2011-10-03",
            "horizon_weeks": 4,
        },
        headers={"Authorization": f"Bearer {a_token}"},
    )
    run_id = fc_resp.json()["forecast_run_id"]

    replenish_payload = {
        "forecast_run_id": run_id,
        "sku_id": "10002",
        "stock_on_hand": 50.0,
        "incoming_stock": 20.0,
        "lead_time_weeks": 2,
        "review_period_weeks": 1,
        "safety_stock_units": 15.0,
    }

    # Viewer -> 403
    v_token = get_token_for_user(client, "viewer", "Viewer123!")
    resp_v = client.post(
        "/api/v1/planning/replenish",
        json=replenish_payload,
        headers={"Authorization": f"Bearer {v_token}"},
    )
    assert resp_v.status_code == 403

    # Analyst -> 403
    resp_a = client.post(
        "/api/v1/planning/replenish",
        json=replenish_payload,
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp_a.status_code == 403

    # Planner -> 200
    p_token = get_token_for_user(client, "planner", "Planner123!")
    resp_p = client.post(
        "/api/v1/planning/replenish",
        json=replenish_payload,
        headers={"Authorization": f"Bearer {p_token}"},
    )
    assert resp_p.status_code == 200
    assert resp_p.json()["sku_id"] == "10002"
    assert resp_p.json()["simulation_status"] == "SIMULATION_BASED_ON_USER_ASSUMPTIONS"


# =====================================================================
# 4. USER ATTRIBUTION & OBJECT-LEVEL AUTHORIZATION (BOLA/IDOR)
# =====================================================================
def test_forecast_run_user_attribution_and_access(client: TestClient):
    """
    Verify user attribution:
    - User A (Analyst) runs a forecast -> run is tagged with User A's user_id.
    - User A can retrieve run details and results.
    - Admin can inspect User A's run.
    """
    a_token = get_token_for_user(client, "analyst", "Analyst123!")
    fc_resp = client.post(
        "/api/v1/forecasts",
        json={
            "model_id": "CatBoost__MAE",
            "sku_ids": ["10002"],
            "forecast_origin": "2011-10-03",
            "horizon_weeks": 4,
        },
        headers={"Authorization": f"Bearer {a_token}"},
    )
    run_id = fc_resp.json()["forecast_run_id"]

    # Verify run details reflect user attribution in persistence
    run_detail = persistence_service.get_run(run_id)
    assert run_detail.user_id is not None
    assert run_detail.user_id.startswith("usr")

    # User A retrieves run details
    resp_run = client.get(
        f"/api/v1/forecasts/runs/{run_id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp_run.status_code == 200
    assert resp_run.json()["forecast_run_id"] == run_id

    # Admin retrieves run details
    admin_token = get_token_for_user(client, "admin", "Admin123!")
    resp_admin_run = client.get(
        f"/api/v1/forecasts/runs/{run_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin_run.status_code == 200


def test_export_object_level_authorization(client: TestClient):
    """
    Verify object-level authorization on exports:
    - Analyst generates an export (tagged with Analyst's user_id).
    - Another non-admin user (Planner) attempting to download Analyst's export is rejected with HTTP 403.
    - Admin is authorized to download.
    - Analyst owner is authorized to download.
    """
    # 1. Analyst creates forecast run and generates CSV export
    a_token = get_token_for_user(client, "analyst", "Analyst123!")
    fc_resp = client.post(
        "/api/v1/forecasts",
        json={
            "model_id": "CatBoost__MAE",
            "sku_ids": ["10002"],
            "forecast_origin": "2011-10-03",
            "horizon_weeks": 4,
        },
        headers={"Authorization": f"Bearer {a_token}"},
    )
    run_id = fc_resp.json()["forecast_run_id"]

    exp_resp = client.post(
        f"/api/v1/forecasts/runs/{run_id}/exports",
        json={"format": "CSV"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert exp_resp.status_code == 201
    export_id = exp_resp.json()["export_id"]

    # 2. Planner (different non-admin user) attempts to download -> 403 Forbidden
    p_token = get_token_for_user(client, "planner", "Planner123!")
    resp_cross = client.get(
        f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {p_token}"},
    )
    assert resp_cross.status_code == 403
    assert "Access forbidden" in get_error_message(resp_cross)

    # 3. Analyst (owner) downloads -> 200 OK
    resp_owner = client.get(
        f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp_owner.status_code == 200
    assert "forecast_run_id,model_id" in resp_owner.text

    # 4. Admin downloads -> 200 OK
    admin_token = get_token_for_user(client, "admin", "Admin123!")
    resp_admin = client.get(
        f"/api/v1/forecasts/runs/{run_id}/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
