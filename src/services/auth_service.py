"""
Authentication and Role-Based Access Control (RBAC) Service.
Implements NIST/OWASP compliant PBKDF2 password hashing, HS256 JWT sessions,
token revocation blacklist, and user management with SQLite persistence.
"""
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.core.config import settings
from src.core.logging_config import logger

DEFAULT_JWT_EXPIRY_MINUTES = 120
PBKDF2_ITERATIONS = 600_000  # OWASP 2023/2024 Password Storage Cheat Sheet standard


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with 16-byte random salt and 600,000 iterations."""
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${salt}${derived.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored PBKDF2-HMAC-SHA256 hash across any iteration count."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        algo_iter, salt, expected_hash = parts
        _, _, iterations_str = algo_iter.split(":")
        iterations = int(iterations_str)

        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt),
            iterations,
        )
        return hmac.compare_digest(derived.hex(), expected_hash)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Checks whether the password hash needs upgrading to the OWASP recommended 600,000 iterations."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return True
        algo_iter, _, _ = parts
        _, _, iterations_str = algo_iter.split(":")
        return int(iterations_str) < PBKDF2_ITERATIONS
    except Exception:
        return True


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data_str: str) -> bytes:
    padding = "=" * (4 - (len(data_str) % 4)) if len(data_str) % 4 != 0 else ""
    return base64.urlsafe_b64decode((data_str + padding).encode("utf-8"))


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    secret_key: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, str, int]:
    """
    Creates an HMAC-SHA256 signed JSON Web Token (JWT) adhering to RFC 8725 best practices.
    Returns (token_string, jti, exp_timestamp).
    """
    key = (secret_key or getattr(settings, "JWT_SECRET_KEY", "forecast-secret-key-prod-2026-auth-hardened")).encode("utf-8")
    now = int(time.time())
    expire_minutes = getattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", DEFAULT_JWT_EXPIRY_MINUTES)
    delta = expires_delta or timedelta(minutes=expire_minutes)
    exp = now + int(delta.total_seconds())
    jti = uuid.uuid4().hex

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "nbf": now,
        "exp": exp,
        "jti": jti,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    token = f"{header_b64}.{payload_b64}.{sig_b64}"
    return token, jti, exp


def decode_access_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Decodes and cryptographically validates a JWT token according to RFC 8725:
    1. Rejects invalid token structure or non-HS256 algorithms.
    2. Validates constant-time cryptographic signature.
    3. Enforces mandatory expiration claim and rejects expired tokens.
    4. Validates issued-at (iat) and not-before (nbf) timestamps with 5s clock skew.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, sig_b64 = parts

    # 1. Validate header algorithm whitelist
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid token header: {e}")

    permitted_alg = getattr(settings, "JWT_ALGORITHM", "HS256")
    if header.get("alg") != permitted_alg:
        raise ValueError(f"Algorithm '{header.get('alg')}' is not permitted. Only {permitted_alg} is authorized.")
    if header.get("typ") != "JWT":
        raise ValueError("Invalid token type")

    # 2. Cryptographic signature check
    key = (secret_key or getattr(settings, "JWT_SECRET_KEY", "forecast-secret-key-prod-2026-auth-hardened")).encode("utf-8")
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    # 3. Payload and temporal claims verification
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid token payload: {e}")

    now = int(time.time())
    clock_skew = 5  # 5 seconds clock drift allowance

    if "exp" not in payload:
        raise ValueError("Token missing mandatory 'exp' claim")
    if payload["exp"] < now:
        raise ValueError("Token has expired")
    if "nbf" in payload and payload["nbf"] > now + clock_skew:
        raise ValueError("Token not yet valid (nbf in future)")
    if "iat" in payload and payload["iat"] > now + clock_skew:
        raise ValueError("Token issued in the future (iat in future)")

    return payload


AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    revoked_at_utc TEXT NOT NULL,
    expires_at_utc INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_jti ON revoked_tokens(jti);
"""


class AuthService:
    """Service handling user accounts, authentication, JWT tokens, and role enforcement."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or getattr(settings, "DATABASE_PATH", settings.DATA_DIR / "storage" / "forecasting_runs.db")
        self._ensure_storage_dir()
        self.init_auth_db()

    def _ensure_storage_dir(self) -> None:
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_auth_db(self) -> None:
        """Initializes tables and seeds default user roles if empty."""
        with self.get_connection() as conn:
            conn.executescript(AUTH_SCHEMA_SQL)
            conn.commit()

        # Seed default test accounts if users table is empty
        self._seed_default_users()

    def _seed_default_users(self) -> None:
        default_accounts = [
            ("usr-admin-001", "admin", "Admin123!", "System Administrator", "admin"),
            ("usr-analyst-001", "analyst", "Analyst123!", "Senior Demand Forecaster", "analyst"),
            ("usr-planner-001", "planner", "Planner123!", "Inventory Supply Planner", "planner"),
            ("usr-viewer-001", "viewer", "Viewer123!", "Executive Stakeholder", "viewer"),
        ]
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for uid, uname, pwd, fname, role in default_accounts:
                cursor.execute("SELECT user_id FROM users WHERE username = ?", (uname,))
                if not cursor.fetchone():
                    h_pwd = hash_password(pwd)
                    cursor.execute(
                        """
                        INSERT INTO users (user_id, username, hashed_password, full_name, role, is_active, created_at_utc)
                        VALUES (?, ?, ?, ?, ?, 1, ?)
                        """,
                        (uid, uname, h_pwd, fname, role, now_str)
                    )
            conn.commit()

    def authenticate_user(self, username: str, plain_password: str) -> Optional[Dict[str, Any]]:
        """Authenticates username and password against SQLite store. Automatically upgrades hash to 600k iterations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
            row = cursor.fetchone()
            if not row:
                return None
            if not verify_password(plain_password, row["hashed_password"]):
                return None

            # Transparent hash migration to OWASP 600k iterations
            if needs_rehash(row["hashed_password"]):
                new_hash = hash_password(plain_password)
                cursor.execute(
                    "UPDATE users SET hashed_password = ? WHERE user_id = ?",
                    (new_hash, row["user_id"])
                )
                conn.commit()
                logger.info(f"Transparently upgraded PBKDF2 hash for user '{username}' to {PBKDF2_ITERATIONS} iterations.")

            return dict(row)

    def bootstrap_admin(self, admin_password: str, force: bool = False) -> Dict[str, Any]:
        """Creates or resets the initial administrator account with a secure password."""
        now_str = datetime.now(timezone.utc).isoformat()
        h_pwd = hash_password(admin_password)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = 'admin'")
            existing = cursor.fetchone()
            if existing:
                if not force:
                    raise ValueError("Admin account already exists. Pass force=True to reset credentials.")
                cursor.execute(
                    "UPDATE users SET hashed_password = ?, is_active = 1 WHERE username = 'admin'",
                    (h_pwd,)
                )
                user_id = existing["user_id"]
            else:
                user_id = "usr-admin-001"
                cursor.execute(
                    """
                    INSERT INTO users (user_id, username, hashed_password, full_name, role, is_active, created_at_utc)
                    VALUES (?, 'admin', ?, 'System Administrator', 'admin', 1, ?)
                    """,
                    (user_id, h_pwd, now_str)
                )
            conn.commit()
        return self.get_user_by_id(user_id)

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a new user record."""
        valid_roles = {"admin", "analyst", "planner", "viewer"}
        if role.lower() not in valid_roles:
            raise ValueError(f"Invalid role '{role}'. Must be one of {valid_roles}")

        user_id = f"usr-{secrets.token_hex(6)}"
        h_pwd = hash_password(password)
        now_str = datetime.now(timezone.utc).isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, username, hashed_password, full_name, role, is_active, created_at_utc)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (user_id, username.strip(), h_pwd, full_name, role.lower(), now_str)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"Username '{username}' already exists")

        return self.get_user_by_id(user_id)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, role, is_active, created_at_utc FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, role, is_active, created_at_utc FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_users(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, role, is_active, created_at_utc FROM users ORDER BY created_at_utc ASC")
            return [dict(r) for r in cursor.fetchall()]

    def revoke_token(self, jti: str, exp: int) -> None:
        """Adds a token's JTI to the revocation blacklist."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO revoked_tokens (jti, revoked_at_utc, expires_at_utc) VALUES (?, ?, ?)",
                (jti, now_str, exp)
            )
            conn.commit()

    def is_token_revoked(self, jti: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,))
            return cursor.fetchone() is not None
