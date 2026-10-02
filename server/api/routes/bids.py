"""
Bids routes — buyer places bids against listings, seller accepts/rejects.

When a seller accepts a bid, the feasibility check is triggered:
1. FEASIBLE → trade executed, listing updated
2. PARTIAL → reduced amount offered to both parties  
3. REJECTED → no trade, reason surfaced

Every outcome produces a ledger entry (including rejections) for audit trail.
"""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional

from ledger.database import mongodb
from ledger.hash_chain import append_trade
from api.auth import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bids", tags=["Bids"])


# --- Schemas ---

class PlaceBidRequest(BaseModel):
    listing_id: str
    requested_amount_kwh: float = Field(gt=0, le=1000)
    offered_price_per_kwh: float = Field(gt=0, le=100)


class RespondBidRequest(BaseModel):
    action: str = Field(pattern="^(accept|reject)$")


# --- Routes ---

@router.post("", status_code=status.HTTP_201_CREATED)
async def place_bid(
    request: PlaceBidRequest,
    user: dict = Depends(require_role("buyer")),
):
    """Place a bid on a listing (buyer only)."""

    # Verify listing exists and is open
    listing = await mongodb.db["listings"].find_one({"listing_id": request.listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["status"] != "open":
        raise HTTPException(status_code=400, detail="This listing is no longer open")

    # Validate amount
    if request.requested_amount_kwh > listing["amount_kwh_available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Requested amount exceeds available ({listing['amount_kwh_available']} kWh)",
        )

    # Prevent bidding on own listing
    if listing["seller_user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")

    # Check for existing pending bid from same buyer on same listing
    existing = await mongodb.db["bids"].find_one({
        "listing_id": request.listing_id,
        "buyer_user_id": user["id"],
        "status": "pending",
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have a pending bid on this listing",
        )

    bid_id = str(uuid.uuid4())[:12]
    bid_doc = {
        "bid_id": bid_id,
        "listing_id": request.listing_id,
        "buyer_user_id": user["id"],
        "buyer_name": user["name"],
        "bus_id": user["bus_id"],
        "requested_amount_kwh": request.requested_amount_kwh,
        "offered_price_per_kwh": request.offered_price_per_kwh,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }

    await mongodb.db["bids"].insert_one(bid_doc)
    bid_doc.pop("_id", None)

    logger.info(f"Bid placed: {bid_id} by {user['name']} on listing {request.listing_id}")
    return bid_doc


@router.post("/{bid_id}/respond")
async def respond_to_bid(
    bid_id: str,
    request: RespondBidRequest,
    user: dict = Depends(require_role("seller")),
):
    """
    Accept or reject a bid (seller only).
    
    On accept: triggers feasibility check → trade execution.
    On reject: marks bid as rejected, no trade.
    """

    bid = await mongodb.db["bids"].find_one({"bid_id": bid_id})
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if bid["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Bid is already {bid['status']}")

    # Verify this bid is on the seller's listing
    listing = await mongodb.db["listings"].find_one({"listing_id": bid["listing_id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Associated listing not found")
    if listing["seller_user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only respond to bids on your own listings")

    if request.action == "reject":
        await mongodb.db["bids"].update_one(
            {"bid_id": bid_id},
            {"$set": {"status": "rejected"}},
        )

        # Still log the rejection in the ledger for audit trail (per spec §2.4.6)
        trade_data = {
            "trade_id": str(uuid.uuid4())[:12],
            "timestamp": datetime.now(timezone.utc),
            "buyer_bus": bid["bus_id"],
            "seller_bus": user["bus_id"],
            "buyer_user_id": bid["buyer_user_id"],
            "seller_user_id": user["id"],
            "buyer_household_id": f"user_{bid['buyer_user_id'][:8]}",
            "seller_household_id": f"user_{user['id'][:8]}",
            "amount_kwh": bid["requested_amount_kwh"],
            "price_per_kwh": bid["offered_price_per_kwh"],
            "total_price": round(bid["requested_amount_kwh"] * bid["offered_price_per_kwh"], 4),
            "status": "rejected",
            "feasibility": None,
            "simulation_timestep": 0,
        }
        await append_trade(trade_data)

        logger.info(f"Bid {bid_id} rejected by {user['name']}")
        return {"status": "rejected", "bid_id": bid_id, "message": "Bid rejected by seller."}

    # --- ACCEPT: Run GNN feasibility check ---
    # The GNN model is the primary (and only) feasibility checker.
    # No pandapower dependency here — uses standalone_checker.
    
    trade_id = str(uuid.uuid4())[:12]
    agreed_amount = bid["requested_amount_kwh"]
    agreed_price = bid["offered_price_per_kwh"]

    # Run GNN feasibility check
    from market.standalone_checker import get_gnn_checker

    checker = get_gnn_checker()
    feasibility_result = checker.check_feasibility(
        seller_bus=user["bus_id"],
        buyer_bus=bid["bus_id"],
        amount_kwh=agreed_amount,
    )

    # Determine trade outcome based on feasibility
    if feasibility_result["is_feasible"]:
        final_status = "executed"
        final_amount = agreed_amount
        reason = None
        logger.info(
            f"Trade {trade_id}: GNN FEASIBLE "
            f"(confidence={feasibility_result['confidence']:.3f}, "
            f"method={feasibility_result['check_method']}, "
            f"time={feasibility_result.get('inference_time_ms', 0):.1f}ms)"
        )
    else:
        # INFEASIBLE — try partial fill via binary search
        max_feasible = checker.find_max_feasible_amount(
            seller_bus=user["bus_id"],
            buyer_bus=bid["bus_id"],
            max_amount_kwh=agreed_amount,
        )

        if max_feasible and max_feasible >= 0.1:
            final_status = "partial_fill"
            final_amount = max_feasible
            reason = (
                f"Only {max_feasible:.3f} of {agreed_amount:.3f} kWh could be "
                f"safely delivered without grid violations"
            )
            logger.info(
                f"Trade {trade_id}: PARTIAL FILL "
                f"({agreed_amount:.3f} → {max_feasible:.3f} kWh)"
            )
        else:
            final_status = "rejected"
            final_amount = 0.0
            violated = []
            if feasibility_result.get("violated_buses"):
                violated.append(
                    f"Voltage violations at buses: {feasibility_result['violated_buses']}"
                )
            if feasibility_result.get("violated_lines"):
                violated.append(
                    f"Line overloads: {feasibility_result['violated_lines']}"
                )
            reason = ". ".join(violated) if violated else (
                feasibility_result.get("reason", "Trade would cause grid violations")
            )
            logger.info(f"Trade {trade_id}: REJECTED by GNN ({reason})")

    # Update bid status
    bid_status_map = {
        "executed": "accepted",
        "partial_fill": "feasibility_partial",
        "rejected": "feasibility_rejected",
    }
    await mongodb.db["bids"].update_one(
        {"bid_id": bid_id},
        {"$set": {
            "status": bid_status_map.get(final_status, "accepted"),
            "final_amount_kwh": final_amount,
        }},
    )

    # Update listing
    if final_status in ("executed", "partial_fill"):
        remaining = listing["amount_kwh_available"] - final_amount
        listing_status = "closed" if remaining <= 0.01 else "partially_filled"
        await mongodb.db["listings"].update_one(
            {"listing_id": listing["listing_id"]},
            {"$set": {
                "amount_kwh_available": max(0, remaining),
                "status": listing_status,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    # Create ledger entry (ALL outcomes get recorded per spec §2.4.6)
    trade_data = {
        "trade_id": trade_id,
        "timestamp": datetime.now(timezone.utc),
        "buyer_bus": bid["bus_id"],
        "seller_bus": user["bus_id"],
        "buyer_user_id": bid["buyer_user_id"],
        "seller_user_id": user["id"],
        "buyer_household_id": f"user_{bid['buyer_user_id'][:8]}",
        "seller_household_id": f"user_{user['id'][:8]}",
        "amount_kwh": final_amount,
        "price_per_kwh": agreed_price,
        "total_price": round(final_amount * agreed_price, 4),
        "original_amount_kwh": agreed_amount if final_status == "partial_fill" else None,
        "status": final_status,
        "feasibility": feasibility_result,
        "simulation_timestep": 0,
    }
    await append_trade(trade_data)

    logger.info(f"Bid {bid_id} accepted → trade {trade_id} ({final_status})")

    # Build response
    response = {
        "status": final_status,
        "bid_id": bid_id,
        "trade_id": trade_id,
        "amount_kwh": final_amount,
        "price_per_kwh": agreed_price,
        "total_price": round(final_amount * agreed_price, 4),
        "feasibility_method": feasibility_result.get("check_method", "unknown"),
        "inference_time_ms": feasibility_result.get("inference_time_ms", 0),
    }

    if final_status == "executed":
        response["message"] = (
            f"Trade executed: {final_amount:.3f} kWh at ₹{agreed_price}/kWh. "
            f"GNN feasibility check passed (confidence: {feasibility_result['confidence']:.1%})."
        )
    elif final_status == "partial_fill":
        response["message"] = reason or f"Partial fill: {final_amount:.3f} kWh delivered."
        response["original_amount_kwh"] = agreed_amount
    elif final_status == "rejected":
        response["message"] = reason or "Trade blocked: would cause grid violations."
        response["feasibility"] = feasibility_result

    return response


@router.get("/mine")
async def get_my_bids(user: dict = Depends(get_current_user)):
    """Get the current user's bids (buyer) or bids on their listings (seller)."""
    
    if user["role"] == "buyer":
        cursor = mongodb.db["bids"].find(
            {"buyer_user_id": user["id"]},
            {"_id": 0},
        ).sort("created_at", -1)
    elif user["role"] == "seller":
        # Get all bids on this seller's listings
        listings = await mongodb.db["listings"].find(
            {"seller_user_id": user["id"]},
            {"listing_id": 1},
        ).to_list(length=100)
        listing_ids = [l["listing_id"] for l in listings]
        
        cursor = mongodb.db["bids"].find(
            {"listing_id": {"$in": listing_ids}},
            {"_id": 0},
        ).sort("created_at", -1)
    else:
        return []

    return await cursor.to_list(length=200)


@router.get("/for-listing/{listing_id}")
async def get_bids_for_listing(
    listing_id: str,
    user: dict = Depends(require_role("seller")),
):
    """Get all bids for a specific listing (seller only)."""
    
    listing = await mongodb.db["listings"].find_one({"listing_id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor = mongodb.db["bids"].find(
        {"listing_id": listing_id},
        {"_id": 0},
    ).sort("created_at", -1)

    return await cursor.to_list(length=100)
