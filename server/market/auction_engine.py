"""
Double auction market engine for P2P energy trading.

Implements a continuous double auction where:
- Sellers (solar households with surplus) post asks (minimum price they'll accept)
- Buyers (households needing power) post bids (maximum price they'll pay)
- Trades match when bid price ≥ ask price
- Clearing price = midpoint of matched bid and ask prices

The auction engine is purely economic — it matches trades on price.
Physical grid feasibility is checked AFTER matching by the feasibility gate
(market/feasibility_gate.py). This separation is intentional: the paper's
argument is that economic-only matching (this file) is insufficient and
needs the physics-aware gate to prevent grid violations.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from heapq import heappush, heappop

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """A bid or ask order in the auction."""
    order_id: str
    household_id: str
    bus_id: int
    is_buy: bool          # True = bid (buyer), False = ask (seller)
    quantity_kwh: float   # Energy quantity
    price_per_kwh: float  # Price limit (max for buyer, min for seller)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    remaining_kwh: float = 0.0

    def __post_init__(self):
        if self.remaining_kwh == 0.0:
            self.remaining_kwh = self.quantity_kwh


@dataclass
class MatchedTrade:
    """A trade matched by the auction engine (pre-feasibility check)."""
    trade_id: str
    buyer_order: Order
    seller_order: Order
    amount_kwh: float
    clearing_price: float   # Midpoint of bid and ask
    buyer_bus: int
    seller_bus: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DoubleAuctionEngine:
    """
    Continuous double auction for P2P energy trading.

    Order books are maintained as priority heaps:
    - Buy orders (bids): sorted by price DESCENDING (highest bidder first)
    - Sell orders (asks): sorted by price ASCENDING (lowest asker first)

    A match occurs when the highest bid ≥ lowest ask.
    Clearing price = (bid + ask) / 2 (midpoint convention, documented in paper).
    """

    def __init__(self):
        self.buy_orders: List[Tuple[float, str, Order]] = []   # (-price, id, order) — max-heap via negation
        self.sell_orders: List[Tuple[float, str, Order]] = []   # (price, id, order) — min-heap
        self.matched_trades: List[MatchedTrade] = []
        self.trade_history: List[MatchedTrade] = []

    def submit_order(self, order: Order) -> Optional[MatchedTrade]:
        """
        Submit a new order and attempt to match it immediately.

        Returns a MatchedTrade if a match is found, None otherwise.
        """
        if order.is_buy:
            heappush(self.buy_orders, (-order.price_per_kwh, order.order_id, order))
        else:
            heappush(self.sell_orders, (order.price_per_kwh, order.order_id, order))

        return self._try_match()

    def submit_bulk_orders(self, orders: List[Order]) -> List[MatchedTrade]:
        """
        Submit multiple orders and match all possible trades.

        Used at the start of each simulation timestep when all households
        submit their bids/asks simultaneously.
        """
        for order in orders:
            if order.is_buy:
                heappush(self.buy_orders, (-order.price_per_kwh, order.order_id, order))
            else:
                heappush(self.sell_orders, (order.price_per_kwh, order.order_id, order))

        matches = []
        while True:
            match = self._try_match()
            if match is None:
                break
            matches.append(match)

        return matches

    def _try_match(self) -> Optional[MatchedTrade]:
        """
        Try to match the best bid with the best ask.

        Match condition: highest bid price ≥ lowest ask price.
        Clearing price: midpoint of the two prices.
        """
        if not self.buy_orders or not self.sell_orders:
            return None

        # Peek at best bid (highest price) and best ask (lowest price)
        best_bid = self.buy_orders[0]  # (-price, id, order)
        best_ask = self.sell_orders[0]  # (price, id, order)

        bid_price = -best_bid[0]
        ask_price = best_ask[0]

        # Match condition
        if bid_price < ask_price:
            return None  # No match possible

        # Pop both orders
        _, _, buyer_order = heappop(self.buy_orders)
        _, _, seller_order = heappop(self.sell_orders)

        # Determine trade quantity (minimum of what buyer wants and seller offers)
        trade_quantity = min(buyer_order.remaining_kwh, seller_order.remaining_kwh)

        # Clearing price at midpoint
        clearing_price = (bid_price + ask_price) / 2.0

        # Update remaining quantities
        buyer_order.remaining_kwh -= trade_quantity
        seller_order.remaining_kwh -= trade_quantity

        # Re-insert partially filled orders
        if buyer_order.remaining_kwh > 0.01:  # Tolerance for floating point
            heappush(self.buy_orders, (-buyer_order.price_per_kwh, buyer_order.order_id, buyer_order))

        if seller_order.remaining_kwh > 0.01:
            heappush(self.sell_orders, (seller_order.price_per_kwh, seller_order.order_id, seller_order))

        # Create matched trade
        trade = MatchedTrade(
            trade_id=str(uuid.uuid4())[:12],
            buyer_order=buyer_order,
            seller_order=seller_order,
            amount_kwh=round(trade_quantity, 3),
            clearing_price=round(clearing_price, 4),
            buyer_bus=buyer_order.bus_id,
            seller_bus=seller_order.bus_id,
        )

        self.matched_trades.append(trade)
        self.trade_history.append(trade)

        logger.debug(
            f"Trade matched: {trade.seller_order.household_id} → "
            f"{trade.buyer_order.household_id}, "
            f"{trade.amount_kwh} kWh @ ₹{trade.clearing_price}/kWh"
        )

        return trade

    def clear_order_books(self):
        """Clear all pending orders (called at end of each timestep)."""
        self.buy_orders.clear()
        self.sell_orders.clear()
        self.matched_trades.clear()

    def get_order_book_summary(self) -> Dict:
        """Get a summary of current order book state."""
        return {
            "num_bids": len(self.buy_orders),
            "num_asks": len(self.sell_orders),
            "best_bid": -self.buy_orders[0][0] if self.buy_orders else None,
            "best_ask": self.sell_orders[0][0] if self.sell_orders else None,
            "spread": (
                self.sell_orders[0][0] - (-self.buy_orders[0][0])
                if self.buy_orders and self.sell_orders
                else None
            ),
            "total_matched": len(self.trade_history),
        }


def generate_orders_from_household_states(
    household_states: Dict[str, Dict],
    base_price_per_kwh: float = 6.0,   # Base electricity price (₹/kWh)
    price_spread: float = 2.0,          # Random price variation range
    min_trade_kwh: float = 0.1,         # Minimum trade quantity
) -> List[Order]:
    """
    Generate auction orders from current household states.

    Sellers: households with solar surplus → ask orders (sell surplus)
    Buyers: households with net load → bid orders (buy cheaper solar power)

    Pricing logic:
    - Sellers ask slightly below grid rate (incentive for buyers to buy local)
    - Buyers bid slightly above feed-in rate (incentive for sellers to sell local)
    - Both are better off than pure grid interaction (the value proposition of P2P)
    """
    import numpy as np
    rng = np.random.default_rng()

    orders = []

    for hh_id, state in household_states.items():
        surplus = state.get("surplus_kw", 0)
        load = state.get("load_kw", 0)
        solar = state.get("solar_kw", 0)
        bus_id = state["bus_id"]
        has_solar = state.get("has_solar", False)

        if has_solar and surplus > min_trade_kwh:
            # Seller: post ask at below-grid-rate (incentivize local buying)
            ask_price = base_price_per_kwh * (0.5 + rng.random() * 0.3)  # 50-80% of grid rate
            order = Order(
                order_id=str(uuid.uuid4())[:8],
                household_id=hh_id,
                bus_id=bus_id,
                is_buy=False,
                quantity_kwh=round(surplus * 0.25, 3),  # Convert 15-min kW to kWh
                price_per_kwh=round(ask_price, 2),
            )
            orders.append(order)

        elif not has_solar and load > min_trade_kwh:
            # Buyer: post bid at below-grid-rate (still cheaper than grid)
            bid_price = base_price_per_kwh * (0.6 + rng.random() * 0.3)  # 60-90% of grid rate
            order = Order(
                order_id=str(uuid.uuid4())[:8],
                household_id=hh_id,
                bus_id=bus_id,
                is_buy=True,
                quantity_kwh=round(load * 0.25 * rng.uniform(0.3, 0.8), 3),  # Portion of load
                price_per_kwh=round(bid_price, 2),
            )
            orders.append(order)

    return orders
