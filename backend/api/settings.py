"""Settings API — user-configurable risk weights and preferences."""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.config import settings
from backend.api.auth import require_auth
from backend.models.user import User

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


def _default_weights() -> RiskWeights:
    return RiskWeights(
        sentiment=settings.risk_weight_sentiment,
        anomaly=settings.risk_weight_anomaly,
        ticket_volume=settings.risk_weight_ticket_volume,
        revenue=settings.risk_weight_revenue,
        engagement=settings.risk_weight_engagement,
    )


def _load_user_weights(tenant_id: str) -> RiskWeights:
    """Load tenant-scoped weight overrides from disk, or return defaults."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                tenants = data.get("tenants", {})
                if tenant_id in tenants:
                    return RiskWeights(**tenants[tenant_id].get("risk_weights", {}))
                # Backward compatibility: legacy global shape.
                if "risk_weights" in data:
                    return RiskWeights(**data.get("risk_weights", {}))
    except Exception:
        pass
    return _default_weights()


def _save_user_weights(tenant_id: str, weights: RiskWeights) -> None:
    """Persist tenant-scoped weight overrides to disk."""
    data: dict = {}
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
    except Exception:
        pass

    tenants = data.get("tenants", {})
    tenant_entry = tenants.get(tenant_id, {})
    tenant_entry["risk_weights"] = weights.model_dump()
    tenants[tenant_id] = tenant_entry
    data["tenants"] = tenants

    with open(_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/risk-weights", response_model=RiskWeights)
async def get_risk_weights(user: User = Depends(require_auth)):
    """Get current risk weight configuration."""
    return _load_user_weights(user.tenant_id)


@router.put("/risk-weights", response_model=RiskWeights)
async def update_risk_weights(weights: RiskWeights, user: User = Depends(require_auth)):
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
    _save_user_weights(user.tenant_id, weights)
    logger.info(f"Risk weights updated: {weights.model_dump()}")
    return weights


@router.delete("/risk-weights", response_model=RiskWeights)
async def reset_risk_weights(user: User = Depends(require_auth)):
    """Reset risk weights to defaults."""
    defaults = _default_weights()
    _save_user_weights(user.tenant_id, defaults)
    logger.info("Risk weights reset to defaults")
    return defaults


@router.get("", response_model=SettingsResponse)
async def get_settings(user: User = Depends(require_auth)):
    """Get overall application settings (read-only view)."""
    return SettingsResponse(
        risk_weights=_load_user_weights(user.tenant_id),
        retention_days=settings.retention_days,
        use_mock_ml=settings.use_mock_ml,
        llm_enabled=bool(settings.openai_api_key),
    )
