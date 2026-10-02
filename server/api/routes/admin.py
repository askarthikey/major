"""
Admin routes — stats dashboard and system management (admin only).
"""

from fastapi import APIRouter, Depends
from ledger.database import mongodb
from api.auth import require_role

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def get_admin_stats(user: dict = Depends(require_role("admin"))):
    """
    Aggregate stats for the admin dashboard:
    - Total trades (full / partial / rejected)
    - Total energy traded
    - Active listings count
    - Registered sellers/buyers count
    - Feasibility rejection rate
    """

    # Trade stats pipeline
    trade_pipeline = [
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

    trade_result = await mongodb.trades.aggregate(trade_pipeline).to_list(length=1)
    trade_stats = trade_result[0] if trade_result else {
        "total_trades": 0, "total_executed": 0, "total_rejected": 0,
        "total_partial": 0, "total_energy_kwh": 0, "total_revenue": 0,
        "avg_price": 0,
    }
    trade_stats.pop("_id", None)

    # User counts
    seller_count = await mongodb.db["users"].count_documents({"role": "seller"})
    buyer_count = await mongodb.db["users"].count_documents({"role": "buyer"})

    # Active listings
    active_listings = await mongodb.db["listings"].count_documents({"status": "open"})

    # Pending bids
    pending_bids = await mongodb.db["bids"].count_documents({"status": "pending"})

    # Feasibility rejection rate
    total_checked = trade_stats["total_trades"]
    violations_prevented = trade_stats["total_rejected"] + trade_stats["total_partial"]
    rejection_rate = round(violations_prevented / max(1, total_checked), 4)

    return {
        **trade_stats,
        "violations_prevented": violations_prevented,
        "rejection_rate": rejection_rate,
        "active_listings": active_listings,
        "pending_bids": pending_bids,
        "registered_sellers": seller_count,
        "registered_buyers": buyer_count,
    }
