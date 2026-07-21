from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    SECRET_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ADMIN_EMAILS: str = ""
    SQL_ECHO: bool = False
    SQL_LOG_JSON: bool = True
    RUN_SCHEMA_BOOTSTRAP: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    CATALOG_CACHE_TTL_SECONDS: int = 300
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    DEFAULT_RATE_LIMIT_PER_MINUTE: int = 120
    UPLOAD_RATE_LIMIT_PER_MINUTE: int = 20
    AUTH_RATE_LIMIT_PER_MINUTE: int = 30
    SHUTDOWN_DRAIN_TIMEOUT_SECONDS: float = 10.0

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "shisha-guid"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_URL: str | None = None
    API_PUBLIC_URL: str | None = None
    MAX_UPLOAD_BYTES: int = 5242880
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Default chosen for inexpensive RU/UK chat behavior via OpenRouter; override
    # in production if stronger reasoning or stricter JSON adherence is needed.
    OPENROUTER_MODEL: str = "sao10k/l3-lunaris-8b"
    AGENT_CATALOG_LIMIT: int = 300
    AGENT_RATE_LIMIT_PER_MINUTE: int = 12
    REVIEW_RATE_LIMIT_PER_DAY: int = 30
    OPENAI_API_KEY: str | None = None
    OPENAI_TRANSCRIBE_MODEL: str = "whisper-1"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

    @property
    def admin_email_set(self) -> set[str]:
        return {
            email.strip().casefold()
            for email in self.ADMIN_EMAILS.split(",")
            if email.strip()
        }


settings = Settings()
