"""Application configuration.

All secrets are read from environment variables.  Never commit a real .env file.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Shopora AI Shopping Agent"
    app_version: str = "3.0.0"
    environment: str = Field(default="development", pattern="^(development|test|staging|production)$")
    debug: bool = False

    database_url: str = "sqlite:///./data/products.db"
    redis_url: str = "redis://localhost:6379/0"
    langgraph_database_url: str | None = None

    groq_api_key: str | None = None
    model_name: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    cors_origins: str = "http://localhost:5173"
    allowed_hosts: str = "localhost,127.0.0.1"
    max_request_body_bytes: int = 1_000_000
    rate_limit_per_minute: int = 60

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    jwt_algorithm: str = "HS256"
    refresh_cookie_name: str = "shopora_refresh"
    refresh_cookie_samesite: str = "lax"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    semantic_search_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    def validate_production(self) -> None:
        if self.environment == "production":
            if not self.groq_api_key:
                raise ValueError("GROQ_API_KEY is required in production")
            if self.secret_key == "change-me-in-production":
                raise ValueError("SECRET_KEY must be changed in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production must use a server database, not SQLite")
            if not self.langgraph_database_url:
                raise ValueError("LANGGRAPH_DATABASE_URL is required in production")
            if self.refresh_cookie_samesite not in {"lax", "strict", "none"}:
                raise ValueError("REFRESH_COOKIE_SAMESITE must be lax, strict, or none")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings


settings = get_settings()

# Backward-compatible names used by the current codebase.
GROQ_API_KEY = settings.groq_api_key
MODEL_NAME = settings.model_name
