"""SignalForge configuration loaded from environment variables."""

from __future__ import annotations

import json
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./signalforge.db",
        alias="DATABASE_URL",
    )
    auto_create_schema: bool = Field(default=True, alias="AUTO_CREATE_SCHEMA")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(default='["http://localhost:3000"]', alias="CORS_ORIGINS")
    app_env: str = Field(default="development", alias="APP_ENV")

    # API Keys (optional — demo data used when missing)
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")
    zendesk_subdomain: str = Field(default="", alias="ZENDESK_SUBDOMAIN")
    zendesk_email: str = Field(default="", alias="ZENDESK_EMAIL")
    zendesk_api_key: str = Field(default="", alias="ZENDESK_API_KEY")
    stripe_api_key: str = Field(default="", alias="STRIPE_API_KEY")
    pagerduty_api_key: str = Field(default="", alias="PAGERDUTY_API_KEY")
    alpha_vantage_key: str = Field(default="", alias="ALPHA_VANTAGE_KEY")

    # Risk Scoring Weights
    risk_weight_sentiment: float = Field(default=0.25, alias="RISK_WEIGHT_SENTIMENT")
    risk_weight_anomaly: float = Field(default=0.25, alias="RISK_WEIGHT_ANOMALY")
    risk_weight_ticket_volume: float = Field(default=0.20, alias="RISK_WEIGHT_TICKET_VOLUME")
    risk_weight_revenue: float = Field(default=0.15, alias="RISK_WEIGHT_REVENUE")
    risk_weight_engagement: float = Field(default=0.15, alias="RISK_WEIGHT_ENGAGEMENT")

    # ML
    use_mock_ml: bool = Field(default=True, alias="USE_MOCK_ML")
    enable_demo_data: bool = Field(default=True, alias="ENABLE_DEMO_DATA")

    # Supabase Auth
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")

    # Legacy JWT (fallback when Supabase not configured)
    jwt_secret: str = Field(default="change-me-in-production-signalforge-2024", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, alias="JWT_EXPIRE_MINUTES")

    # Notifications — Email (Resend)
    resend_api_key: str = Field(default="", alias="RESEND_API_KEY")
    notification_from_email: str = Field(default="alerts@signalforge.io", alias="NOTIFICATION_FROM_EMAIL")

    # Notifications — Slack
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")

    # LLM (optional — falls back to keyword search when not set)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")

    # Data retention
    retention_days: int = Field(default=90, alias="RETENTION_DAYS")

    # FAISS index persistence
    faiss_index_path: str = Field(default="./faiss_index", alias="FAISS_INDEX_PATH")

    # Ingestion
    reddit_subreddits: str = Field(default="technology,sysadmin,netsec", alias="REDDIT_SUBREDDITS")
    newsapi_categories: str = Field(default="technology,business", alias="NEWSAPI_CATEGORIES")
    newsapi_keywords: str = Field(default="cybersecurity,outage,data breach", alias="NEWSAPI_KEYWORDS")
    zendesk_ticket_statuses: str = Field(default="new,open,pending,hold", alias="ZENDESK_TICKET_STATUSES")
    stripe_event_types: str = Field(
        default="charge.failed,invoice.payment_failed,payout.failed,charge.dispute.created",
        alias="STRIPE_EVENT_TYPES",
    )
    pagerduty_service_ids: str = Field(default="", alias="PAGERDUTY_SERVICE_IDS")
    alpha_vantage_symbols: str = Field(default="AAPL,MSFT,SPY", alias="ALPHA_VANTAGE_SYMBOLS")
    ingestion_interval_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("INGESTION_INTERVAL_SECONDS", "INGESTION_INTERVAL"),
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if not raw:
            return []

        # Supports JSON list format and comma-separated format.
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                pass

        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
