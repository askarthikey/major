"""
Trade routes — CRUD endpoints for the trade ledger.
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional, List
from datetime import datetime

from ledger.database import mongodb
from ledger.hash_chain import verify_chain
from api.schemas import TradeResponse, TradeStatsResponse, ChainVerificationResponse
from api.auth import get_current_user, require_role

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("/mine")
async def get_my_trades(
    limit: int = Query(default=50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Get the current user's own trade history (buyer or seller)."""
    query = {
        "$or": [
            {"buyer_user_id": user["id"]},
            {"seller_user_id": user["id"]},
        ]
    }

    cursor = mongodb.trades.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)

    return await cursor.to_list(length=limit)


@router.get("/all")
async def get_all_trades(
    limit: int = Query(default=100, ge=1, le=1000),
    skip: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None),
    buyer_id: Optional[str] = Query(default=None),
    seller_id: Optional[str] = Query(default=None),
    user: dict = Depends(require_role("admin")),
):
    """Get ALL trades in the system (admin only). Supports filters."""
    query = {}
    if status_filter:
        query["status"] = status_filter
    if buyer_id:
        query["buyer_user_id"] = buyer_id
    if seller_id:
        query["seller_user_id"] = seller_id

    cursor = mongodb.trades.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).skip(skip).limit(limit)

    total = await mongodb.trades.count_documents(query)
    trades = await cursor.to_list(length=limit)

    return {"trades": trades, "total": total}


@router.get("/stats", response_model=TradeStatsResponse)
async def get_trade_stats():
    """Get aggregate trade statistics."""
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_trades": {"$sum": 1},
                "total_executed": {
                    "$sum": {"$cond": [{"$in": ["$status", ["executed", "completed"]]}, 1, 0]}
                },
                "total_rejected": {
                    "$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}
                },
                "total_partial": {
                    "$sum": {"$cond": [{"$eq": ["$status", "partial_fill"]}, 1, 0]}
                },
                "total_under_delivered": {
                    "$sum": {"$cond": [{"$eq": ["$status", "under_delivered"]}, 1, 0]}
                },
                "total_energy_kwh": {
                    "$sum": {"$cond": [
                        {"$in": ["$status", ["executed", "partial_fill", "completed", "under_delivered"]]},
                        {"$ifNull": ["$actual_delivered_kwh", "$amount_kwh"]}, 0
                    ]}
                },
                "total_scheduled_kwh": {
                    "$sum": {"$cond": [
                        {"$in": ["$status", ["executed", "partial_fill", "completed", "under_delivered"]]},
                        {"$ifNull": ["$scheduled_kwh", "$amount_kwh"]}, 0
                    ]}
                },
                "total_revenue": {
                    "$sum": {"$cond": [
                        {"$in": ["$status", ["executed", "partial_fill", "completed", "under_delivered"]]},
                        "$total_price", 0
                    ]}
                },
                "avg_price": {"$avg": "$price_per_kwh"},
            }
        }
    ]

    result = await mongodb.trades.aggregate(pipeline).to_list(length=1)

    if result:
        data = result[0]
        data.pop("_id", None)
        data["violations_prevented"] = data["total_rejected"] + data["total_partial"]
        return data

    return TradeStatsResponse(
        total_trades=0, total_executed=0, total_rejected=0,
        total_partial=0, total_energy_kwh=0, total_revenue=0,
        avg_price=0, violations_prevented=0,
    )


@router.get("/verify-chain", response_model=ChainVerificationResponse)
async def verify_trade_chain(
    limit: Optional[int] = Query(default=None, ge=1),
):
    """Verify the hash chain integrity of the trade ledger."""
    result = await verify_chain(limit=limit)
    return result


@router.get("", response_model=List[TradeResponse])
async def get_trades(
    limit: int = Query(default=50, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
):
    """Get trades from the ledger, most recent first."""
    query = {}
    if status:
        query["status"] = status

    cursor = mongodb.trades.find(
        query,
        {"_id": 0},
    ).sort("timestamp", -1).skip(skip).limit(limit)

    trades = await cursor.to_list(length=limit)
    return trades


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str):
    """Get a single trade by ID."""
    trade = await mongodb.trades.find_one(
        {"trade_id": trade_id},
        {"_id": 0},
    )
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    return trade


@router.get("/{trade_id}/delivery")
async def get_trade_delivery(trade_id: str):
    """Get detailed delivery information for a trade."""
    trade = await mongodb.trades.find_one(
        {"trade_id": trade_id},
        {"_id": 0},
    )
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")

    delivery = trade.get("delivery")
    if not delivery:
        raise HTTPException(
            status_code=404,
            detail=f"Trade {trade_id} has no delivery data (may be rejected or pending)",
        )

    return {
        "trade_id": trade_id,
        "status": trade.get("status"),
        "scheduled_kwh": trade.get("scheduled_kwh"),
        "actual_delivered_kwh": trade.get("actual_delivered_kwh"),
        "original_amount_kwh": trade.get("original_amount_kwh"),
        "listing_original_kwh": trade.get("listing_original_kwh"),
        "listing_remaining_kwh": trade.get("listing_remaining_kwh"),
        "delivery": delivery,
    }
