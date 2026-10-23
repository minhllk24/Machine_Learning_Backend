"""
Pydantic v2 schemas for Authentication and RBAC endpoints.
"""
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="Account username")
    password: str = Field(..., min_length=6, description="Account plaintext password")


class UserProfileResponse(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="User full display name")
    role: str = Field(..., description="Assigned RBAC role: admin, analyst, planner, viewer")
    is_active: bool = Field(True, description="Account active status")
    created_at_utc: str = Field(..., description="Timestamp of account creation")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="HS256 signed JWT bearer token")
    token_type: str = Field("bearer", description="Token authorization type")
    expires_in_seconds: int = Field(..., description="Token lifespan in seconds")
    user: UserProfileResponse = Field(..., description="Authenticated user profile")


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="New account username")
    password: str = Field(..., min_length=6, description="Account initial password")
    role: str = Field(..., description="Role assignment: admin, analyst, planner, viewer")
    full_name: Optional[str] = Field(None, description="Optional full display name")


class LogoutResponse(BaseModel):
    status: str = Field("SUCCEEDED", description="Logout execution status")
    message: str = Field("Session successfully terminated and token revoked", description="Human-readable message")


class BootstrapAdminRequest(BaseModel):
    admin_password: str = Field(..., min_length=8, description="Secure initial password for administrator")
    force: bool = Field(False, description="Whether to reset password if admin already exists")

