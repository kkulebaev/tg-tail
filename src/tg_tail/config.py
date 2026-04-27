from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    tg_api_id: int
    tg_api_hash: SecretStr
    tg_session: SecretStr

    channel_ids: list[str] = Field(default_factory=list)

    database_url: str

    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: SecretStr
    s3_bucket: str
    s3_region: str = "us-east-1"

    log_level: str = "INFO"
    log_format: str = "json"

    media_concurrency: int = 3
    media_poll_interval_seconds: float = 5.0
    media_max_attempts: int = 5
    media_max_bytes: int = 100 * 1024 * 1024

    @field_validator("channel_ids", mode="before")
    @classmethod
    def split_channels(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("database_url", mode="after")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        return v


def get_settings() -> Settings:
    return Settings()
