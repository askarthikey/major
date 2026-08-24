"""
Trade routes — CRUD endpoints for the trade ledger.
"""

from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime

from ledger.database import mongodb
from ledger.hash_chain import verify_chain
from api.schemas import TradeResponse, TradeStatsResponse, ChainVerificationResponse

router = APIRouter(prefix="/trades", tags=["Trades"])


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


@router.get("/stats", response_model=TradeStatsResponse)
async def get_trade_stats():
    """Get aggregate trade statistics."""
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_trades": {"$sum": 1},
                "total_executed": {
                    "$sum": {"$cond": [{"$eq": ["$status", "executed"]}, 1, 0]}
                },
                "total_rejected": {
                    "$sum": {"$cond": [{"$eq": ["$status", "rejected"]}, 1, 0]}
                },
                "total_partial": {
                    "$sum": {"$cond": [{"$eq": ["$status", "partial_fill"]}, 1, 0]}
                },
                "total_energy_kwh": {
                    "$sum": {"$cond": [
                        {"$in": ["$status", ["executed", "partial_fill"]]},
                        "$amount_kwh", 0
                    ]}
                },
                "total_revenue": {
                    "$sum": {"$cond": [
                        {"$in": ["$status", ["executed", "partial_fill"]]},
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
        # Count violations prevented = rejected + partial fill
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


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str):
    """Get a single trade by ID."""
    trade = await mongodb.trades.find_one(
        {"trade_id": trade_id},
        {"_id": 0},
    )
    if not trade:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    return trade
