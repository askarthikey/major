"""
Authentication routes — signup, login, and current user info.
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from ledger.database import mongodb
from api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Request / Response schemas ---

class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(pattern="^(seller|buyer)$")  # admin is NOT self-service
    bus_id: int = Field(ge=0, le=12, description="Bus on the IEEE 13-bus feeder this user represents")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    bus_id: Optional[int] = None
    created_at: str


# --- Routes ---

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """Register a new seller or buyer account."""

    # Check email uniqueness
    existing = await mongodb.db["users"].find_one({"email": request.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Check bus_id isn't already taken by the same role
    existing_bus = await mongodb.db["users"].find_one({
        "bus_id": request.bus_id,
        "role": request.role,
    })
    if existing_bus:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {request.role} is already registered on bus {request.bus_id}",
        )

    user_id = str(uuid.uuid4())
    user_doc = {
        "_id": user_id,
        "name": request.name,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "role": request.role,
        "bus_id": request.bus_id,
        "created_at": datetime.now(timezone.utc),
    }

    await mongodb.db["users"].insert_one(user_doc)
    logger.info(f"New {request.role} registered: {request.email} (bus {request.bus_id})")

    # Issue JWT
    token = create_access_token({
        "sub": user_id,
        "email": request.email,
        "role": request.role,
    })

    return AuthResponse(
        access_token=token,
        user={
            "id": user_id,
            "name": request.name,
            "email": request.email,
            "role": request.role,
            "bus_id": request.bus_id,
            "created_at": user_doc["created_at"].isoformat(),
        },
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Authenticate and return a JWT."""

    user = await mongodb.db["users"].find_one({"email": request.email})
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
    })

    logger.info(f"User logged in: {user['email']} ({user['role']})")

    return AuthResponse(
        access_token=token,
        user={
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "bus_id": user.get("bus_id"),
            "created_at": user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"]),
        },
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return UserResponse(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        role=user["role"],
        bus_id=user.get("bus_id"),
        created_at=user["created_at"].isoformat() if isinstance(user["created_at"], datetime) else str(user["created_at"]),
    )
