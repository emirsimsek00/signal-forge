"""SignalForge — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import init_db

from backend.api.signals import router as signals_router
from backend.api.incidents import router as incidents_router
from backend.api.dashboard import router as dashboard_router
from backend.api.websocket import router as websocket_router
from backend.api.correlation import router as correlation_router
from backend.workers.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup
    await init_db()
    print("✦ SignalForge API started")
    print(f"  Mock ML: {settings.use_mock_ml}")
    print(f"  Database: {settings.database_url}")
    print(f"  Ingestion interval: {settings.ingestion_interval_seconds}s")

    # Start background scheduler
    await scheduler.start()

    yield

    # Shutdown
    await scheduler.stop()
    print("✦ SignalForge API shutting down")


app = FastAPI(
    title="SignalForge",
    description="Multimodal AI Operations Copilot — Intelligence API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(signals_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
app.include_router(websocket_router)
app.include_router(correlation_router)


@app.get("/api/health")
async def health_check():
    from backend.api.websocket import manager as ws_manager
    return {
        "status": "healthy",
        "service": "signalforge",
        "version": "0.2.0",
        "websocket_connections": ws_manager.connection_count,
        "scheduler_active": scheduler._running,
    }
