"""
SHA-256 hash chain for tamper-evident trade ledger.

Each trade record's hash is computed from its content + the previous record's hash,
forming an append-only chain. Any modification to a historical record breaks the chain,
making tampering detectable.

This is NOT a blockchain — there's no distributed consensus, no proof-of-work,
no token economics. It's a simple cryptographic audit trail, which is all that's
needed for this use case and avoids the infrastructure complexity of real blockchain
with zero loss of research value.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ledger.database import mongodb

logger = logging.getLogger(__name__)

# Genesis hash — the "previous hash" for the very first trade record
GENESIS_HASH = hashlib.sha256(b"solar-p2p-genesis-block").hexdigest()


def compute_trade_hash(trade_data: Dict[str, Any], prev_hash: str) -> str:
    """
    Compute SHA-256 hash of a trade record's content + previous hash.
    
    The hash covers all trade-relevant fields (not the hash fields themselves)
    to ensure any modification to the trade content is detectable.
    
    Args:
        trade_data: Trade record dictionary (without hash fields).
        prev_hash: Hash of the previous trade record in the chain.
    
    Returns:
        Hex-encoded SHA-256 hash string.
    """
    # Select the fields that are part of the hash computation
    # (exclude this_hash and prev_hash — they're computed, not input)
    hash_content = {
        "trade_id": trade_data.get("trade_id", ""),
        "timestamp": str(trade_data.get("timestamp", "")),
        "buyer_bus": trade_data.get("buyer_bus", 0),
        "seller_bus": trade_data.get("seller_bus", 0),
        "buyer_household_id": trade_data.get("buyer_household_id", ""),
        "seller_household_id": trade_data.get("seller_household_id", ""),
        "amount_kwh": trade_data.get("amount_kwh", 0),
        "price_per_kwh": trade_data.get("price_per_kwh", 0),
        "total_price": trade_data.get("total_price", 0),
        "status": trade_data.get("status", ""),
        "simulation_timestep": trade_data.get("simulation_timestep", 0),
        "prev_hash": prev_hash,
    }

    # Deterministic JSON serialization (sorted keys, no whitespace variance)
    content_string = json.dumps(hash_content, sort_keys=True, default=str)
    return hashlib.sha256(content_string.encode("utf-8")).hexdigest()


async def get_last_hash() -> str:
    """
    Retrieve the hash of the most recent trade record in the chain.
    Returns GENESIS_HASH if no trades exist yet.
    """
    last_trade = await mongodb.trades.find_one(
        sort=[("timestamp", -1)],
        projection={"this_hash": 1},
    )
    if last_trade and "this_hash" in last_trade:
        return last_trade["this_hash"]
    return GENESIS_HASH


async def append_trade(trade_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append a trade record to the hash chain and persist to MongoDB.
    
    1. Gets the last hash in the chain.
    2. Computes this record's hash (content + prev_hash).
    3. Stores the record with both hash fields set.
    
    Args:
        trade_data: Trade record dictionary.
    
    Returns:
        The stored trade record with hash fields populated.
    """
    prev_hash = await get_last_hash()
    this_hash = compute_trade_hash(trade_data, prev_hash)

    trade_data["prev_hash"] = prev_hash
    trade_data["this_hash"] = this_hash

    # Convert datetime objects for MongoDB
    if isinstance(trade_data.get("timestamp"), datetime):
        trade_data["timestamp"] = trade_data["timestamp"]

    await mongodb.trades.insert_one(trade_data)
    logger.info(
        f"Trade {trade_data.get('trade_id', 'unknown')} appended to chain "
        f"(hash: {this_hash[:12]}...)"
    )
    return trade_data


async def verify_chain(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Walk the entire hash chain and verify integrity.
    
    For each record, recomputes the hash from its content + the previous record's
    hash, and checks it matches the stored hash. Any mismatch indicates tampering.
    
    Args:
        limit: Maximum number of records to verify (None = all).
    
    Returns:
        Dictionary with verification results:
        - valid: bool (True if entire chain is intact)
        - total_records: int
        - records_checked: int
        - first_broken_at: Optional[int] (index of first broken link)
        - errors: List of error descriptions
    """
    cursor = mongodb.trades.find(sort=[("timestamp", 1)])
    if limit:
        cursor = cursor.limit(limit)

    records = await cursor.to_list(length=limit or 100000)

    result = {
        "valid": True,
        "total_records": len(records),
        "records_checked": 0,
        "first_broken_at": None,
        "errors": [],
    }

    expected_prev_hash = GENESIS_HASH

    for i, record in enumerate(records):
        result["records_checked"] = i + 1

        # Check prev_hash links to the previous record
        stored_prev_hash = record.get("prev_hash", "")
        if stored_prev_hash != expected_prev_hash:
            result["valid"] = False
            if result["first_broken_at"] is None:
                result["first_broken_at"] = i
            result["errors"].append(
                f"Record {i} (trade_id={record.get('trade_id', '?')}): "
                f"prev_hash mismatch — expected {expected_prev_hash[:12]}..., "
                f"got {stored_prev_hash[:12]}..."
            )

        # Recompute this record's hash and verify
        recomputed_hash = compute_trade_hash(record, stored_prev_hash)
        stored_hash = record.get("this_hash", "")
        if recomputed_hash != stored_hash:
            result["valid"] = False
            if result["first_broken_at"] is None:
                result["first_broken_at"] = i
            result["errors"].append(
                f"Record {i} (trade_id={record.get('trade_id', '?')}): "
                f"content hash mismatch — computed {recomputed_hash[:12]}..., "
                f"stored {stored_hash[:12]}..."
            )

        expected_prev_hash = stored_hash

    logger.info(
        f"Chain verification: {result['records_checked']} records checked, "
        f"valid={result['valid']}"
    )
    return result
