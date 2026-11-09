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
from market.energy_contract import EnergyContract, contract_from_kwh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/listings", tags=["Listings"])


# --- Schemas ---

class CreateListingRequest(BaseModel):
    amount_kwh_available: Optional[float] = Field(default=None, gt=0, le=1000)
    power_kw: Optional[float] = Field(default=None, gt=0, le=1000)
    duration_hours: Optional[float] = Field(default=None, gt=0, le=24)
    asking_price_per_kwh: float = Field(gt=0, le=100)


class UpdateListingRequest(BaseModel):
    amount_kwh_available: Optional[float] = Field(default=None, gt=0, le=1000)
    power_kw: Optional[float] = Field(default=None, gt=0, le=1000)
    duration_hours: Optional[float] = Field(default=None, gt=0, le=24)
    asking_price_per_kwh: Optional[float] = Field(default=None, gt=0, le=100)
    status: Optional[str] = Field(default=None, pattern="^(open|closed)$")


async def _listing_feasibility_preview(contract: EnergyContract, seller_bus: int) -> dict:
    """Estimate safe delivery for every registered buyer without reserving capacity."""
    buyers = await mongodb.db["users"].find(
        {"role": "buyer", "bus_id": {"$ne": None}},
        {"bus_id": 1, "_id": 0},
    ).to_list(length=100)
    if not buyers:
        return {"status": "awaiting_buyer_route", "capacity_reserved": False}

    from market.standalone_checker import get_gnn_checker
    checker = get_gnn_checker()
    routes = []
    for buyer in buyers:
        result = checker.check_feasibility(
            seller_bus=seller_bus,
            buyer_bus=buyer["bus_id"],
            amount_kwh=contract.energy_kwh,
        )
        max_kwh = contract.energy_kwh if result["is_feasible"] else (
            checker.find_max_feasible_amount(
                seller_bus=seller_bus,
                buyer_bus=buyer["bus_id"],
                max_amount_kwh=contract.energy_kwh,
            ) or 0
        )
        routes.append({
            "buyer_bus": buyer["bus_id"],
            "feasible": max_kwh > 0,
            "max_kwh": round(max_kwh, 6),
            "confidence": result.get("confidence", 0),
        })

    safe_kwh = min(route["max_kwh"] for route in routes)
    safe_contract = contract_from_kwh(safe_kwh, contract.duration_hours) if safe_kwh > 0 else None
    return {
        "status": "feasible" if safe_contract else "infeasible",
        "feasible": safe_contract.as_dict() if safe_contract else None,
        "routes": routes,
        "capacity_reserved": False,
    }


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

    if request.power_kw is not None or request.duration_hours is not None:
        if request.power_kw is None or request.duration_hours is None:
            raise HTTPException(status_code=422, detail="Power and duration must be provided together")
        contract = EnergyContract(request.power_kw, request.duration_hours)
    elif request.amount_kwh_available is not None:
        contract = contract_from_kwh(request.amount_kwh_available)
    else:
        raise HTTPException(status_code=422, detail="Provide power and duration")

    preview = await _listing_feasibility_preview(contract, user["bus_id"])

    listing_id = str(uuid.uuid4())[:12]
    listing_doc = {
        "listing_id": listing_id,
        "seller_user_id": user["id"],
        "bus_id": user["bus_id"],
        "amount_kwh_available": contract.energy_kwh,
        "power_kw": contract.power_kw,
        "duration_hours": contract.duration_hours,
        "units_available": contract.units,
        "unit_size_wh": 10,
        "feasibility_preview": preview,
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
    if request.power_kw is not None or request.duration_hours is not None:
        power_kw = request.power_kw if request.power_kw is not None else listing.get("power_kw")
        duration_hours = request.duration_hours if request.duration_hours is not None else listing.get("duration_hours")
        if power_kw is None or duration_hours is None:
            raise HTTPException(status_code=422, detail="Power and duration must be provided together")
        contract = EnergyContract(power_kw, duration_hours)
        update_fields.update({
            "amount_kwh_available": contract.energy_kwh,
            "power_kw": contract.power_kw,
            "duration_hours": contract.duration_hours,
            "units_available": contract.units,
            "unit_size_wh": 10,
        })
    elif request.amount_kwh_available is not None:
        duration_hours = listing.get("duration_hours", 1.0)
        contract = contract_from_kwh(request.amount_kwh_available, duration_hours)
        update_fields.update({
            "amount_kwh_available": contract.energy_kwh,
            "power_kw": contract.power_kw,
            "duration_hours": contract.duration_hours,
            "units_available": contract.units,
            "unit_size_wh": 10,
        })
    if request.asking_price_per_kwh is not None:
        update_fields["asking_price_per_kwh"] = request.asking_price_per_kwh
    if request.status is not None:
        update_fields["status"] = request.status

    if any(value is not None for value in (request.power_kw, request.duration_hours, request.amount_kwh_available)):
        updated_contract = EnergyContract(
            update_fields.get("power_kw", listing.get("power_kw", listing["amount_kwh_available"])),
            update_fields.get("duration_hours", listing.get("duration_hours", 1.0)),
        )
        update_fields["feasibility_preview"] = await _listing_feasibility_preview(
            updated_contract,
            user["bus_id"],
        )

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
