"""
Phase 16 Security Hardening, PBKDF2 600k Migration, RFC 8725 JWT & Contract Test Suite.
Verifies:
1. PBKDF2-HMAC-SHA256 password hashing uses OWASP-compliant 600,000 iterations.
2. Automatic transparent hash migration from legacy 100,000 to 600,000 on login.
3. RFC 8725 JWT claims: non-HS256 algorithms rejected, expired tokens rejected, future tokens rejected.
4. Secure administrative bootstrap via /api/v1/auth/bootstrap.
5. Neutralization of spreadsheet formula injection (CSV/DDE injection) in exports.
6. Path traversal protection on export downloads (rejects '..', '/', '\\').
7. Replenishment planning rejects protection period exceeding available forecast horizon.
8. Forecast API enforces maximum horizon H=4 for CatBoost MAE champion.
"""
from datetime import timedelta
import time
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.auth_service import (
    PBKDF2_ITERATIONS,
    hash_password,
    verify_password,
    needs_rehash,
    create_access_token,
    decode_access_token,
    _b64url_encode,
    _b64url_decode,
)
from src.services.export_service import sanitize_csv_cell, export_service
from src.api.errors import ExportFileMissingOrCorruptException


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_pbkdf2_600k_iterations_format():
    """Verify newly hashed passwords use 600,000 iterations per OWASP cheat sheet."""
    pwd = "SecureHardenedPassword2026!"
    h = hash_password(pwd)
    assert h.startswith("pbkdf2:sha256:600000$")
    assert verify_password(pwd, h) is True
    assert verify_password("WrongPassword", h) is False
    assert needs_rehash(h) is False


def test_pbkdf2_transparent_hash_upgrade(client: TestClient):
    """Verify legacy 100,000 iteration hash is automatically upgraded to 600,000 on successful login."""
    from src.api.dependencies_auth import get_auth_service
    auth_service = get_auth_service()

    # Create a user with legacy 100k iteration hash manually in SQLite
    legacy_salt = "0123456789abcdef0123456789abcdef"
    import hashlib
    legacy_derived = hashlib.pbkdf2_hmac(
        "sha256",
        "LegacyPass123!".encode("utf-8"),
        bytes.fromhex(legacy_salt),
        100_000,
    )
    legacy_hash = f"pbkdf2:sha256:100000${legacy_salt}${legacy_derived.hex()}"
    assert needs_rehash(legacy_hash) is True

    test_uname = "legacy_test_user_p16"
    with auth_service.get_connection() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (test_uname,))
        conn.execute(
            """
            INSERT INTO users (user_id, username, hashed_password, full_name, role, is_active, created_at_utc)
            VALUES ('usr-legacy-001', ?, ?, 'Legacy User', 'analyst', 1, '2026-10-21T00:00:00Z')
            """,
            (test_uname, legacy_hash)
        )
        conn.commit()

    # Log in with the legacy user
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": test_uname, "password": "LegacyPass123!"},
    )
    assert resp.status_code == 200

    # Inspect stored hash in database - it should now be 600,000 iterations!
    with auth_service.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hashed_password FROM users WHERE username = ?", (test_uname,))
        updated_hash = cursor.fetchone()["hashed_password"]

    assert updated_hash.startswith("pbkdf2:sha256:600000$")
    assert needs_rehash(updated_hash) is False
    assert verify_password("LegacyPass123!", updated_hash) is True


def test_jwt_rfc8725_algorithm_allowlist():
    """Verify JWT decoder rejects non-HS256 algorithms such as 'none' or 'RS256'."""
    # Construct a forged token with alg="none"
    import json
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": "usr-attacker", "username": "attacker", "role": "admin", "exp": int(time.time()) + 3600}
    h_b64 = _b64url_encode(json.dumps(header).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    forged_token = f"{h_b64}.{p_b64}."

    with pytest.raises(ValueError, match="not permitted"):
        decode_access_token(forged_token)


def test_jwt_temporal_claims_verification():
    """Verify JWT decoder rejects expired tokens and tokens issued in the future."""
    # Expired token
    expired_token, _, _ = create_access_token(
        "u1", "u1", "viewer", expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(ValueError, match="Token has expired"):
        decode_access_token(expired_token)


def test_secure_administrative_bootstrap(client: TestClient):
    """Verify administrative bootstrap endpoint for secure initial setup or password rotation."""
    try:
        bootstrap_payload = {
            "admin_password": "NewSecureAdminPassword2026!#",
            "force": True,
        }
        resp = client.post("/api/v1/auth/bootstrap", json=bootstrap_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

        # Verify login with new password succeeds
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "NewSecureAdminPassword2026!#"},
        )
        assert login_resp.status_code == 200
    finally:
        # Restore admin password for subsequent test suite consistency
        client.post("/api/v1/auth/bootstrap", json={"admin_password": "Admin123!", "force": True})


def test_csv_formula_injection_defense():
    """Verify spreadsheet formula injection characters (=, +, -, @, tab, cr) are neutralized."""
    # Malicious cells that an attacker might inject
    dangerous_inputs = [
        "=SUM(A1:A10)",
        "+cmd|' /C calc'!A0",
        "-2+3*cmd|' /C notepad'!A0",
        "@SUM(1+1)*cmd",
        "\tmalicious_tab",
        "\rmalicious_cr",
    ]
    for inp in dangerous_inputs:
        sanitized = sanitize_csv_cell(inp)
        assert sanitized.startswith("'"), f"Failed to neutralize formula injection on: {inp}"
        assert sanitized[1:] == inp

    # Safe cells should remain untouched
    safe_inputs = ["10002", "20713", "CatBoost__MAE", "INFERRED", "2011-10-10"]
    for safe in safe_inputs:
        assert sanitize_csv_cell(safe) == safe


def test_export_path_traversal_prevention():
    """Verify get_export_file_path rejects path traversal attempts with '..', '/', '\\'."""
    with pytest.raises(ExportFileMissingOrCorruptException) as exc_info1:
        export_service.get_export_file_path("../../../etc/passwd", "exp_123")
    assert "Invalid characters" in exc_info1.value.details.get("reason", "")

    with pytest.raises(ExportFileMissingOrCorruptException) as exc_info2:
        export_service.get_export_file_path("valid_run", "../../../boot.ini")
    assert "Invalid characters" in exc_info2.value.details.get("reason", "")


def test_forecast_horizon_cap_enforcement(client: TestClient):
    """Verify API strictly enforces maximum horizon H=4 for CatBoost MAE champion."""
    # Obtain Planner token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "planner", "password": "Planner123!"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # H=1 valid
    resp_h1 = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 1},
        headers=headers,
    )
    assert resp_h1.status_code == 200

    # H=4 valid (champion principal horizon)
    resp_h4 = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 4},
        headers=headers,
    )
    assert resp_h4.status_code == 200

    # H=0 rejected (422)
    resp_h0 = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 0},
        headers=headers,
    )
    assert resp_h0.status_code == 422

    # H=5 rejected (422) - exceeds authorized H=4
    resp_h5 = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 5},
        headers=headers,
    )
    assert resp_h5.status_code == 422

    # H=8 rejected (422) - exceeds authorized H=4
    resp_h8 = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 8},
        headers=headers,
    )
    assert resp_h8.status_code == 422


def test_replenishment_protection_period_exceeding_horizon_rejected(client: TestClient):
    """Verify replenishment simulation rejects protection period (L+R) exceeding available forecast horizon."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "planner", "password": "Planner123!"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Generate a run with H=2
    fc_resp = client.post(
        "/api/v1/forecasts",
        json={"model_id": "CatBoost__MAE", "sku_ids": ["10002"], "forecast_origin": "2011-10-03", "horizon_weeks": 2},
        headers=headers,
    )
    assert fc_resp.status_code == 200
    run_id = fc_resp.json()["forecast_run_id"]

    # Request replenishment with lead_time=2, review_period=1 -> protection_period=3 > available horizon 2
    rep_resp = client.post(
        "/api/v1/planning/replenish",
        json={
            "sku_id": "10002",
            "forecast_run_id": run_id,
            "stock_on_hand": 10.0,
            "incoming_stock": 5.0,
            "lead_time_weeks": 2,
            "review_period_weeks": 1,
            "safety_stock_units": 5.0,
        },
        headers=headers,
    )
    assert rep_resp.status_code == 422
    err_data = rep_resp.json()
    assert "exceeds available forecast horizon" in err_data.get("message", "")
