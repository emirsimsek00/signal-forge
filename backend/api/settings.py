"""Settings API — user-configurable risk weights and preferences."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings

logger = logging.getLogger("signalforge.settings")
router = APIRouter(prefix="/api/settings", tags=["settings"])

_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "user_settings.json")


class RiskWeights(BaseModel):
    sentiment: float = 0.25
    anomaly: float = 0.25
    ticket_volume: float = 0.20
    revenue: float = 0.15
    engagement: float = 0.15


class SettingsResponse(BaseModel):
    risk_weights: RiskWeights
    retention_days: int
    use_mock_ml: bool
    llm_enabled: bool


def _load_user_weights() -> RiskWeights:
    """Load saved weight overrides from disk, or return defaults."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                return RiskWeights(**data.get("risk_weights", {}))
    except Exception:
        pass
    return RiskWeights(
        sentiment=settings.risk_weight_sentiment,
        anomaly=settings.risk_weight_anomaly,
        ticket_volume=settings.risk_weight_ticket_volume,
        revenue=settings.risk_weight_revenue,
        engagement=settings.risk_weight_engagement,
    )


def _save_user_weights(weights: RiskWeights) -> None:
    """Persist weight overrides to disk."""
    data = {}
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
    except Exception:
        pass
    data["risk_weights"] = weights.model_dump()
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/risk-weights", response_model=RiskWeights)
async def get_risk_weights():
    """Get current risk weight configuration."""
    return _load_user_weights()


@router.put("/risk-weights", response_model=RiskWeights)
async def update_risk_weights(weights: RiskWeights):
    """Update risk weight configuration.

    Weights should sum to approximately 1.0.
    """
    total = weights.sentiment + weights.anomaly + weights.ticket_volume + weights.revenue + weights.engagement
    if abs(total - 1.0) > 0.01:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Weights must sum to 1.0 (got {total:.2f})",
        )
    _save_user_weights(weights)
    logger.info(f"Risk weights updated: {weights.model_dump()}")
    return weights


@router.delete("/risk-weights", response_model=RiskWeights)
async def reset_risk_weights():
    """Reset risk weights to defaults."""
    defaults = RiskWeights(
        sentiment=0.25,
        anomaly=0.25,
        ticket_volume=0.20,
        revenue=0.15,
        engagement=0.15,
    )
    _save_user_weights(defaults)
    logger.info("Risk weights reset to defaults")
    return defaults


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get overall application settings (read-only view)."""
    return SettingsResponse(
        risk_weights=_load_user_weights(),
        retention_days=settings.retention_days,
        use_mock_ml=settings.use_mock_ml,
        llm_enabled=bool(settings.openai_api_key),
    )
