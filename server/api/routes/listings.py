"""
Listings routes — seller's energy listings (asks).

A listing represents a seller's offer to sell surplus solar energy at a given price.
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

from ledger.database import mongodb
from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/listings", tags=["Listings"])


# --- Schemas ---

class CreateListingRequest(BaseModel):
    amount_kwh_available: float = Field(gt=0, le=1000)
    asking_price_per_kwh: float = Field(gt=0, le=100)


class UpdateListingRequest(BaseModel):
    amount_kwh_available: Optional[float] = Field(default=None, gt=0, le=1000)
    asking_price_per_kwh: Optional[float] = Field(default=None, gt=0, le=100)
    status: Optional[str] = Field(default=None, pattern="^(open|closed)$")


# --- Routes ---

@router.get("")
async def get_listings(
    status_filter: Optional[str] = None,
    bus_id: Optional[int] = None,
):
    """Get all open listings (buyers browsing available energy)."""
    query = {}
    if status_filter:
        query["status"] = status_filter
    else:
        query["status"] = "open"  # Default: show only open listings

    if bus_id is not None:
        query["bus_id"] = bus_id

    cursor = mongodb.db["listings"].find(
        query, {"_id": 0}
    ).sort("created_at", -1)

    listings = await cursor.to_list(length=100)

    # Enrich with seller name
    for listing in listings:
        seller = await mongodb.db["users"].find_one(
            {"_id": listing["seller_user_id"]},
            {"name": 1}
        )
        listing["seller_name"] = seller["name"] if seller else "Unknown"

    return listings


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_listing(
    request: CreateListingRequest,
    user: dict = Depends(require_role("seller")),
):
    """Create a new energy listing (seller only)."""

    # Check if seller already has an open listing
    existing = await mongodb.db["listings"].find_one({
        "seller_user_id": user["id"],
        "status": "open",
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an open listing. Update or close it before creating a new one.",
        )

    listing_id = str(uuid.uuid4())[:12]
    listing_doc = {
        "listing_id": listing_id,
        "seller_user_id": user["id"],
        "bus_id": user["bus_id"],
        "amount_kwh_available": request.amount_kwh_available,
        "asking_price_per_kwh": request.asking_price_per_kwh,
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await mongodb.db["listings"].insert_one(listing_doc)
    listing_doc.pop("_id", None)

    logger.info(f"Listing created: {listing_id} by {user['name']} (bus {user['bus_id']})")
    return listing_doc


@router.patch("/{listing_id}")
async def update_listing(
    listing_id: str,
    request: UpdateListingRequest,
    user: dict = Depends(require_role("seller")),
):
    """Update a listing's price, amount, or status (seller only)."""

    listing = await mongodb.db["listings"].find_one({"listing_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing["seller_user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only update your own listings")

    update_fields = {"updated_at": datetime.now(timezone.utc)}
    if request.amount_kwh_available is not None:
        update_fields["amount_kwh_available"] = request.amount_kwh_available
    if request.asking_price_per_kwh is not None:
        update_fields["asking_price_per_kwh"] = request.asking_price_per_kwh
    if request.status is not None:
        update_fields["status"] = request.status

    await mongodb.db["listings"].update_one(
        {"listing_id": listing_id},
        {"$set": update_fields},
    )

    updated = await mongodb.db["listings"].find_one(
        {"listing_id": listing_id}, {"_id": 0}
    )

    logger.info(f"Listing updated: {listing_id}")
    return updated


@router.get("/mine")
async def get_my_listings(user: dict = Depends(require_role("seller"))):
    """Get the current seller's own listings."""
    cursor = mongodb.db["listings"].find(
        {"seller_user_id": user["id"]},
        {"_id": 0},
    ).sort("created_at", -1)

    return await cursor.to_list(length=50)
