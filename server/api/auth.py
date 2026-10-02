"""
Authentication utilities — JWT creation/verification and password hashing.

Uses python-jose for JWT and bcrypt directly for password hashing.
Choice: localStorage for JWT storage on the frontend (documented per plan §1.2).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from config.settings import settings
from ledger.database import mongodb

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Decoded JWT payload."""
    user_id: str
    email: str
    role: str


def hash_password(password: str) -> str:
    """Hash a plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenData:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role")
        if not user_id or not email or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return TokenData(user_id=user_id, email=email, role=role)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency — extract and validate the current user from the JWT.

    Returns the full user document from MongoDB (minus the password hash).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token_data = decode_access_token(credentials.credentials)

    user = await mongodb.db["users"].find_one(
        {"_id": token_data.user_id},
        {"password_hash": 0},
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    # Normalize _id → id for frontend
    user["id"] = str(user.pop("_id"))
    return user


def require_role(*roles: str):
    """
    Factory for a FastAPI dependency that restricts access to specific roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])

    Or inject the user:
        async def endpoint(user=Depends(require_role("seller"))):
    """
    async def role_checker(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ) -> dict:
        user = await get_current_user(credentials)
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(roles)}",
            )
        return user
    return role_checker
