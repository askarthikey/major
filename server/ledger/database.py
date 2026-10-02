"""
Async MongoDB connection management using Motor.
Provides connection pooling, database/collection initialization,
and graceful lifecycle management for FastAPI.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """Async MongoDB connection manager using Motor."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        """Establish connection to MongoDB Atlas."""
        logger.info("Connecting to MongoDB...")
        self.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=50,
            minPoolSize=10,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[settings.db_name]

        # Verify connection
        try:
            await self.client.admin.command("ping")
            logger.info(f"Connected to MongoDB database: {settings.db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

        # Initialize collections and indexes
        await self._init_collections()

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def _init_collections(self) -> None:
        """Create collections and indexes if they don't exist."""
        # Trades collection
        trades = self.db["trades"]
        await trades.create_index("timestamp")
        await trades.create_index("status")
        await trades.create_index("buyer_bus")
        await trades.create_index("seller_bus")
        await trades.create_index("buyer_user_id")
        await trades.create_index("seller_user_id")
        await trades.create_index([("timestamp", -1)]) # Descending for recent-first queries

        # Grid snapshots collection
        grid_snapshots = self.db["grid_snapshots"]
        await grid_snapshots.create_index("timestamp")
        await grid_snapshots.create_index([("timestamp", -1)])

        # Household profiles collection
        households = self.db["households"]
        await households.create_index("household_id", unique=True)
        await households.create_index("bus_id")

        # Simulation state collection
        sim_state = self.db["simulation_state"]
        await sim_state.create_index("session_id", unique=True)

        # Users collection
        users = self.db["users"]
        await users.create_index("email", unique=True)
        await users.create_index("role")
        await users.create_index("bus_id")

        # Listings collection (seller asks)
        listings = self.db["listings"]
        await listings.create_index("seller_user_id")
        await listings.create_index("bus_id")
        await listings.create_index("status")
        await listings.create_index([("created_at", -1)])

        # Bids collection (buyer offers)
        bids = self.db["bids"]
        await bids.create_index("listing_id")
        await bids.create_index("buyer_user_id")
        await bids.create_index("status")
        await bids.create_index([("created_at", -1)])

        logger.info("MongoDB collections and indexes initialized")

    # --- Collection accessors ---

    @property
    def trades(self):
        """Access the trades collection."""
        return self.db["trades"]

    @property
    def grid_snapshots(self):
        """Access the grid snapshots collection."""
        return self.db["grid_snapshots"]

    @property
    def households(self):
        """Access the households collection."""
        return self.db["households"]

    @property
    def simulation_state(self):
        """Access the simulation state collection."""
        return self.db["simulation_state"]


# Singleton database instance
mongodb = MongoDB()


async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency to get the database instance."""
    return mongodb.db
