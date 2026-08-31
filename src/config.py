"""Application configuration management using Pydantic Settings."""

from enum import Enum
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Application environment enumeration."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class OpenAIModel(str, Enum):
    """Supported OpenAI models."""

    GPT35_TURBO = "gpt-3.5-turbo"
    GPT4_TURBO = "gpt-4-turbo-preview"
    GPT4 = "gpt-4"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_ENV: Environment = Environment.PRODUCTION
    APP_DEBUG: bool = False
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # OpenAI
    OPENAI_API_KEY: str = Field(..., min_length=10)
    OPENAI_MODEL: OpenAIModel = OpenAIModel.GPT4_TURBO
    OPENAI_TEMPERATURE: float = Field(default=0.3, ge=0.0, le=1.0)
    OPENAI_MAX_TOKENS: int = Field(default=300, ge=50, le=1000)

    # GitHub
    GITHUB_TOKEN: str = Field(..., min_length=10)
    GITHUB_WEBHOOK_SECRET: str = Field(..., min_length=10)
    GITHUB_API_BASE_URL: str = "https://api.github.com"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL: int = Field(default=3600, ge=60, le=86400)  # 1 hour default
    REDIS_MAX_CONNECTIONS: int = Field(default=10, ge=1, le=100)

    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = Field(default=60, ge=1, le=1000)

    # File Filtering
    EXCLUDE_FILE_PATTERNS: List[str] = Field(
        default=[
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "*.min.js",
            "*.min.css",
            "*.map",
            "*.lock",
            "go.sum",
            "Cargo.lock",
            "Gemfile.lock",
            "poetry.lock",
        ]
    )
    MAX_FILE_SIZE_BYTES: int = Field(default=1_000_000, ge=100_000)  # 1MB
    MAX_DIFF_LINES: int = Field(default=500, ge=100, le=2000)

    # Features
    ENABLE_BREAKING_CHANGE_DETECTION: bool = True
    ENABLE_REVIEW_TIME_ESTIMATION: bool = True
    ENABLE_REVIEWER_SUGGESTION: bool = True
    ENABLE_PR_LABELING: bool = True

    # Security
    ALLOWED_IPS: Optional[List[str]] = None
    REQUEST_TIMEOUT_SECONDS: int = Field(default=30, ge=5, le=120)

    @field_validator("EXCLUDE_FILE_PATTERNS", mode="before")
    @classmethod
    def parse_exclude_patterns(cls, value) -> List[str]:
        """Parse comma-separated string into list of patterns."""
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        """Validate Redis URL format."""
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return value

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "forbid"


# Singleton instance
settings = Settings()