"""
FastAPI dependency providers for Authentication and Role-Based Access Control.
Enforces HTTP 401 on unauthenticated requests and HTTP 403 on role violations.
"""
from typing import Any, Callable, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, status

from src.services.auth_service import AuthService, decode_access_token

_auth_service_instance: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Dependency provider returning singleton AuthService instance."""
    global _auth_service_instance
    if _auth_service_instance is None:
        _auth_service_instance = AuthService()
    return _auth_service_instance


async def get_current_user(
    authorization: Optional[str] = Header(None, description="Bearer JWT access token"),
    auth_service: AuthService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """
    Extracts, decodes, and validates the Bearer JWT token from the Authorization header.
    Rejects missing, expired, revoked, or signature-invalid tokens with HTTP 401.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Expected 'Authorization: Bearer <token>' header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check revocation blacklist
    jti = payload.get("jti")
    if jti and auth_service.is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = auth_service.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach token JTI and exp to user object for logout tracking
    user_dict = dict(user)
    user_dict["_jti"] = jti
    user_dict["_exp"] = payload.get("exp")
    return user_dict


async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> Optional[Dict[str, Any]]:
    """Optional user dependency for endpoints allowing guest/legacy access with enhanced context."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization, auth_service)
    except HTTPException:
        return None


def require_role(allowed_roles: List[str]) -> Callable:
    """
    Factory dependency creating a role-enforcement guard.
    Returns HTTP 403 FORBIDDEN if the authenticated user's role is not permitted.
    """
    normalized_allowed = [r.lower() for r in allowed_roles]

    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role", "").lower()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: User with role '{user_role}' is not authorized. "
                    f"Required roles: {allowed_roles}"
                ),
            )
        return current_user

    return role_checker
