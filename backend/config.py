"""SignalForge configuration loaded from environment variables."""

from __future__ import annotations

import json
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./signalforge.db",
        alias="DATABASE_URL",
    )

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(default='["http://localhost:3000"]', alias="CORS_ORIGINS")

    # API Keys (optional — demo data used when missing)
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")

    # Risk Scoring Weights
    risk_weight_sentiment: float = Field(default=0.25, alias="RISK_WEIGHT_SENTIMENT")
    risk_weight_anomaly: float = Field(default=0.25, alias="RISK_WEIGHT_ANOMALY")
    risk_weight_ticket_volume: float = Field(default=0.20, alias="RISK_WEIGHT_TICKET_VOLUME")
    risk_weight_revenue: float = Field(default=0.15, alias="RISK_WEIGHT_REVENUE")
    risk_weight_engagement: float = Field(default=0.15, alias="RISK_WEIGHT_ENGAGEMENT")

    # ML
    use_mock_ml: bool = Field(default=True, alias="USE_MOCK_ML")

    @property
    def cors_origins_list(self) -> list[str]:
        return json.loads(self.cors_origins)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
