import json
import logging
import sys

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

if settings.SQL_ECHO and settings.SQL_LOG_JSON:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            json.dumps(
                {
                    "level": "%(levelname)s",
                    "logger": "%(name)s",
                    "message": "%(message)s",
                }
            )
        )
    )
    sql_logger = logging.getLogger("sqlalchemy.engine")
    sql_logger.handlers = [handler]
    sql_logger.setLevel(logging.INFO)
    sql_logger.propagate = False

engine = create_async_engine(
    db_url,
    echo=settings.SQL_ECHO and not settings.SQL_LOG_JSON,
    pool_pre_ping=True,
    pool_recycle=1800,
)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
