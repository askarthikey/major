"""
Tests for the market engine (Layer 3).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from market.auction_engine import (
    DoubleAuctionEngine,
    Order,
    generate_orders_from_household_states,
)


class TestDoubleAuction:
    """Tests for the double auction matching engine."""

    def test_match_when_bid_exceeds_ask(self):
        engine = DoubleAuctionEngine()
        seller = Order(
            order_id="s1", household_id="HH_01", bus_id=2,
            is_buy=False, quantity_kwh=1.0, price_per_kwh=3.0,
        )
        buyer = Order(
            order_id="b1", household_id="HH_02", bus_id=7,
            is_buy=True, quantity_kwh=1.0, price_per_kwh=5.0,
        )
        engine.submit_order(seller)
        trade = engine.submit_order(buyer)
        assert trade is not None
        assert trade.clearing_price == 4.0  # Midpoint of 3 and 5

    def test_no_match_when_bid_below_ask(self):
        engine = DoubleAuctionEngine()
        seller = Order(
            order_id="s1", household_id="HH_01", bus_id=2,
            is_buy=False, quantity_kwh=1.0, price_per_kwh=5.0,
        )
        buyer = Order(
            order_id="b1", household_id="HH_02", bus_id=7,
            is_buy=True, quantity_kwh=1.0, price_per_kwh=3.0,
        )
        engine.submit_order(seller)
        trade = engine.submit_order(buyer)
        assert trade is None

    def test_partial_fill(self):
        engine = DoubleAuctionEngine()
        seller = Order(
            order_id="s1", household_id="HH_01", bus_id=2,
            is_buy=False, quantity_kwh=2.0, price_per_kwh=3.0,
        )
        buyer = Order(
            order_id="b1", household_id="HH_02", bus_id=7,
            is_buy=True, quantity_kwh=1.0, price_per_kwh=5.0,
        )
        engine.submit_order(seller)
        trade = engine.submit_order(buyer)
        assert trade is not None
        assert trade.amount_kwh == 1.0
        # Seller should still have 1 kWh remaining
        assert len(engine.sell_orders) == 1

    def test_bulk_matching(self):
        engine = DoubleAuctionEngine()
        orders = [
            Order(order_id="s1", household_id="HH_01", bus_id=2,
                  is_buy=False, quantity_kwh=1.0, price_per_kwh=3.0),
            Order(order_id="s2", household_id="HH_03", bus_id=4,
                  is_buy=False, quantity_kwh=1.0, price_per_kwh=4.0),
            Order(order_id="b1", household_id="HH_02", bus_id=7,
                  is_buy=True, quantity_kwh=1.0, price_per_kwh=5.0),
            Order(order_id="b2", household_id="HH_04", bus_id=5,
                  is_buy=True, quantity_kwh=1.0, price_per_kwh=4.5),
        ]
        matches = engine.submit_bulk_orders(orders)
        assert len(matches) == 2  # Both should match

    def test_order_book_summary(self):
        engine = DoubleAuctionEngine()
        summary = engine.get_order_book_summary()
        assert summary["num_bids"] == 0
        assert summary["num_asks"] == 0

    def test_clear_order_books(self):
        engine = DoubleAuctionEngine()
        engine.submit_order(Order(
            order_id="s1", household_id="HH_01", bus_id=2,
            is_buy=False, quantity_kwh=1.0, price_per_kwh=10.0,
        ))
        engine.clear_order_books()
        assert len(engine.buy_orders) == 0
        assert len(engine.sell_orders) == 0


class TestOrderGeneration:
    """Tests for generating orders from household states."""

    def test_generates_orders(self):
        states = {
            "HH_01": {"bus_id": 2, "has_solar": True, "load_kw": 1.0, "solar_kw": 5.0, "surplus_kw": 4.0},
            "HH_02": {"bus_id": 7, "has_solar": False, "load_kw": 3.0, "solar_kw": 0.0, "surplus_kw": 0.0},
        }
        orders = generate_orders_from_household_states(states)
        assert len(orders) == 2
        sell_orders = [o for o in orders if not o.is_buy]
        buy_orders = [o for o in orders if o.is_buy]
        assert len(sell_orders) == 1
        assert len(buy_orders) == 1
