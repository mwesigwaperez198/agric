from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration loaded from the environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Farm-to-Fork API"
    debug: bool = False
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
    ]

    # Database
    database_url: str = "postgresql+psycopg2://farm:farm@localhost:5432/farmfork"

    # Auth / cryptography
    secret_key: str = "dev-only-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    totp_issuer: str = "Farm-to-Fork"

    # Platform economics
    platform_commission_rate: float = 0.025
    currency: str = "UGX"

    # Payments webhook log (Phase 1 mock endpoint writes here)
    webhook_log_path: str = "data/webhooks.jsonl"

    # Vision / voice providers (empty => mock fallback)
    vision_provider: str = "mock"
    whisper_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Uploads
    upload_dir: str = "data/uploads"
    max_upload_bytes: int = 8 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
