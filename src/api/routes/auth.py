"""
Authentication and User Management Routes.
Implements /api/v1/auth endpoints for login, session status, logout, and admin user provisioning.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from src.services.auth_service import AuthService, create_access_token
from src.api.dependencies_auth import get_auth_service, get_current_user, require_role
from src.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserProfileResponse,
    CreateUserRequest,
    LogoutResponse,
    BootstrapAdminRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate user credentials",
    description="Authenticates username and password, returning an HMAC-SHA256 signed JWT bearer token and user profile.",
)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    user = auth_service.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, jti, exp = create_access_token(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
    )

    profile = UserProfileResponse(
        user_id=user["user_id"],
        username=user["username"],
        full_name=user.get("full_name"),
        role=user["role"],
        is_active=bool(user["is_active"]),
        created_at_utc=user["created_at_utc"],
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=exp - int(user.get("_iat", 0) or 0),
        user=profile,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Terminate active session",
    description="Revokes the active bearer JWT token by adding its JTI to the server revocation blacklist.",
)
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    jti = current_user.get("_jti")
    exp = current_user.get("_exp", 0)
    if jti:
        auth_service.revoke_token(jti, exp)

    return LogoutResponse(
        status="SUCCEEDED",
        message="Session successfully terminated and token revoked.",
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user identity",
    description="Returns profile and active roles for the authenticated token holder.",
)
async def get_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        full_name=current_user.get("full_name"),
        role=current_user["role"],
        is_active=bool(current_user["is_active"]),
        created_at_utc=current_user["created_at_utc"],
    )


@router.get(
    "/users",
    response_model=List[UserProfileResponse],
    summary="List system accounts (Admin Only)",
    description="Returns all registered user accounts and their assigned RBAC roles. Restricted to administrators.",
    dependencies=[Depends(require_role(["admin"]))],
)
async def list_users(
    auth_service: AuthService = Depends(get_auth_service),
) -> List[UserProfileResponse]:
    users = auth_service.list_users()
    return [
        UserProfileResponse(
            user_id=u["user_id"],
            username=u["username"],
            full_name=u.get("full_name"),
            role=u["role"],
            is_active=bool(u["is_active"]),
            created_at_utc=u["created_at_utc"],
        )
        for u in users
    ]


@router.post(
    "/users",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user account (Admin Only)",
    description="Provisions a new user account with specified RBAC role. Restricted to administrators.",
    dependencies=[Depends(require_role(["admin"]))],
)
async def create_user(
    payload: CreateUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    try:
        user = auth_service.create_user(
            username=payload.username,
            password=payload.password,
            role=payload.role,
            full_name=payload.full_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserProfileResponse(
        user_id=user["user_id"],
        username=user["username"],
        full_name=user.get("full_name"),
        role=user["role"],
        is_active=bool(user["is_active"]),
        created_at_utc=user["created_at_utc"],
    )


@router.post(
    "/bootstrap",
    response_model=UserProfileResponse,
    summary="Secure administrative bootstrap",
    description="One-time secure initialization or password rotation of the root administrator account.",
)
async def bootstrap_admin(
    payload: BootstrapAdminRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    try:
        user = auth_service.bootstrap_admin(payload.admin_password, force=payload.force)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserProfileResponse(
        user_id=user["user_id"],
        username=user["username"],
        full_name=user.get("full_name"),
        role=user["role"],
        is_active=bool(user["is_active"]),
        created_at_utc=user["created_at_utc"],
    )

