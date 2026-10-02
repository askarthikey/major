"""
FastAPI application entry point.

This is the main server that ties all layers together:
- Layer 1 (Grid Simulation) via grid_state routes
- Layer 2 (GNN) via the feasibility gate (called during simulation)
- Layer 3 (Market Engine) via simulation routes
- Layer 4 (Dashboard) via trade routes, WebSocket, and grid routes
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from ledger.database import mongodb
from fastapi import WebSocket, WebSocketDisconnect
from api.routes import trades, grid_state, simulation, auth, listings, bids, admin
from api.routes.websocket import manager as ws_manager, websocket_endpoint as ws_handler
from api.middleware import global_exception_handler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # --- Startup ---
    logger.info("🔆 Starting P2P Solar Microgrid Trading System...")

    # Connect to MongoDB
    try:
        await mongodb.connect()
        logger.info("✓ MongoDB connected")
    except Exception as e:
        logger.error(f"✗ MongoDB connection failed: {e}")
        logger.warning("Server will start but database operations will fail")

    logger.info("✓ Server ready")

    yield

    # --- Shutdown ---
    logger.info("Shutting down...")
    await mongodb.disconnect()


# Create FastAPI app
app = FastAPI(
    title="P2P Solar Microgrid Trading API",
    description=(
        "GNN-Constrained Peer-to-Peer Solar Microgrid Trading System. "
        "A solar-power trading platform with an AI safety layer that ensures "
        "no trade accidentally overloads the electrical grid."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(listings.router, prefix="/api")
app.include_router(bids.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(grid_state.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
# WebSocket — registered directly on app (FastAPI 0.141+ include_router WS fix)
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Proxy to the websocket handler in api.routes.websocket."""
    await ws_handler(websocket)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — health check."""
    from market.simulation_loop import get_simulation

    sim = get_simulation()
    return {
        "status": "online",
        "name": "P2P Solar Microgrid Trading API",
        "version": "1.0.0",
        "mongodb_connected": mongodb.client is not None,
        "simulation_running": sim.is_running if sim else False,
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    from market.simulation_loop import get_simulation

    sim = get_simulation()

    health = {
        "status": "healthy",
        "version": "1.0.0",
        "mongodb_connected": False,
        "gnn_model_loaded": False,
        "simulation_running": sim.is_running if sim else False,
    }

    # Check MongoDB
    try:
        if mongodb.client:
            await mongodb.client.admin.command("ping")
            health["mongodb_connected"] = True
    except Exception:
        health["status"] = "degraded"

    return health


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )
