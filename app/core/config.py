from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    APP_NAME: str = "Social Feed API"
    ENVIRONMENT: str = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None
    AWS_REGION: str
    S3_BUCKET_NAME: str
    S3_PUBLIC_BASE_URL: str
    S3_ENDPOINT_URL: str | None = None
    S3_OBJECT_PREFIX: str = "post-images"
    MAX_IMAGE_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_IMAGE_PIXELS: int = 25_000_000

    REDIS_URL: str = "redis://localhost:6379/0"
    RATE_LIMIT_ENABLED: bool = True

    RATE_LIMIT_AUTH_LOGIN_MAX_REQUESTS: int = 10
    RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS: int = 60

    RATE_LIMIT_AUTH_REGISTER_MAX_REQUESTS: int = 5
    RATE_LIMIT_AUTH_REGISTER_WINDOW_SECONDS: int = 900

    RATE_LIMIT_POST_WRITE_MAX_REQUESTS: int = 20
    RATE_LIMIT_POST_WRITE_WINDOW_SECONDS: int = 60

    RATE_LIMIT_COMMENT_WRITE_MAX_REQUESTS: int = 40
    RATE_LIMIT_COMMENT_WRITE_WINDOW_SECONDS: int = 60

    RATE_LIMIT_LIKE_WRITE_MAX_REQUESTS: int = 120
    RATE_LIMIT_LIKE_WRITE_WINDOW_SECONDS: int = 60

    RATE_LIMIT_UPLOAD_MAX_REQUESTS: int = 10
    RATE_LIMIT_UPLOAD_WINDOW_SECONDS: int = 300

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
