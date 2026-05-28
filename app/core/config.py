from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ADMIN_EMAILS: str = ""
    SQL_ECHO: bool = False
    SQL_LOG_JSON: bool = True
    RUN_SCHEMA_BOOTSTRAP: bool = False

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

    class Config:
        env_file = ".env"


settings = Settings()
