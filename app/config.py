from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "DBS Contract Intelligence"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
    ]

    # Database
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/contract_intel",
        validation_alias="DATABASE_URL",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Storage
    storage_path: Path = Path("./storage")
    max_file_size_mb: int = 100
    allowed_extensions: set[str] = {".pdf", ".xlsx", ".xls"}

    # Security
    secret_key: str = Field(
        default="dev-secret-change-in-production", validation_alias="SECRET_KEY"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # AI / LLM
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-large"
    max_tokens: int = 4000

    # OCR
    tesseract_path: str | None = None
    ocr_languages: str = "eng"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()

# Ensure storage directories exist
settings.storage_path.mkdir(parents=True, exist_ok=True)
(settings.storage_path / "uploads").mkdir(exist_ok=True)
(settings.storage_path / "processed").mkdir(exist_ok=True)
(settings.storage_path / "reports").mkdir(exist_ok=True)
