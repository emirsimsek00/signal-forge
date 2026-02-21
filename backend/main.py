"""SignalForge — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.database import init_db
from backend.logging_config import setup_logging

from backend.api.auth import router as auth_router
from backend.api.signals import router as signals_router
from backend.api.incidents import router as incidents_router
from backend.api.dashboard import router as dashboard_router
from backend.api.websocket import router as websocket_router
from backend.api.correlation import router as correlation_router
from backend.api.chat import router as chat_router
from backend.api.anomaly import router as anomaly_router
from backend.api.brief import router as brief_router
from backend.api.forecast import router as forecast_router
from backend.api.webhooks import router as webhooks_router
from backend.api.demo import router as demo_router
from backend.api.simulator import router as simulator_router
from backend.api.settings import router as settings_router
from backend.api.notifications import router as notifications_router
from backend.workers.scheduler import scheduler

logger = logging.getLogger("signalforge")

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def _startup_checks() -> None:
    """Log warnings for misconfigured or missing settings."""
    if settings.jwt_secret == "change-me-in-production-signalforge-2024":
        logger.warning("⚠  JWT_SECRET is using the default value — set a strong secret for production")
    if not settings.openai_api_key:
        logger.info("○ No OPENAI_API_KEY — AI Chat will use keyword search mode")
    if "sqlite" in settings.database_url:
        logger.info("○ Using SQLite — consider PostgreSQL for production workloads")

    api_keys = {
        "Reddit": settings.reddit_client_id,
        "NewsAPI": settings.newsapi_key,
        "Zendesk": settings.zendesk_api_key,
        "Stripe": settings.stripe_api_key,
        "PagerDuty": settings.pagerduty_api_key,
        "Alpha Vantage": settings.alpha_vantage_key,
    }
    active = [name for name, key in api_keys.items() if key]
    if active:
        logger.info(f"✓ Live sources: {', '.join(active)}")
    else:
        logger.info("○ No API keys set — using demo data for all sources")

    # Supabase auth status
    if settings.supabase_url:
        logger.info("✓ Supabase Auth enabled")
    else:
        logger.info("○ Supabase not configured — running in demo auth mode")

    # Notification status
    notif = []
    if settings.resend_api_key:
        notif.append("Resend")
    if settings.slack_webhook_url:
        notif.append("Slack")
    if notif:
        logger.info(f"✓ Notifications: {', '.join(notif)}")
    else:
        logger.info("○ No notification providers configured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()
    _startup_checks()

    # Startup
    await init_db()
    logger.info("✦ SignalForge API started")
    logger.info(f"  Database: {settings.database_url}")
    logger.info(f"  Ingestion interval: {settings.ingestion_interval_seconds}s")

    # Start background scheduler
    await scheduler.start()

    yield

    # Shutdown
    await scheduler.stop()
    logger.info("✦ SignalForge API shutting down")


app = FastAPI(
    title="SignalForge",
    description="Multimodal AI Operations Copilot — Intelligence API",
    version="0.5.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Routers
app.include_router(auth_router)
app.include_router(signals_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
app.include_router(websocket_router)
app.include_router(correlation_router)
app.include_router(chat_router)
app.include_router(anomaly_router)
app.include_router(brief_router)
app.include_router(forecast_router)
app.include_router(webhooks_router)
app.include_router(demo_router)
app.include_router(simulator_router)
app.include_router(settings_router)
app.include_router(notifications_router)


@app.get("/api/health")
async def health_check():
    from backend.api.websocket import manager as ws_manager
    return {
        "status": "healthy",
        "service": "signalforge",
        "version": "0.5.0",
        "websocket_connections": ws_manager.connection_count,
        "scheduler_active": scheduler._running,
    }

