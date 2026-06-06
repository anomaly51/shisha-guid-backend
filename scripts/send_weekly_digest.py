import asyncio
import logging
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.shisha import BowlSetup
from app.models.user import User, UserFollow

logger = logging.getLogger(__name__)


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    since = datetime.utcnow() - timedelta(days=7)

    async with session_factory() as db:
        users = (await db.execute(select(User).where(User.is_banned.is_(False)))).scalars().all()

        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            await engine.dispose()
            return

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
            if settings.SMTP_USE_TLS:
                client.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

            for user in users:
                followed_ids = (
                    await db.execute(
                        select(UserFollow.followed_id).where(UserFollow.follower_id == user.id)
                    )
                ).scalars().all()
                if not followed_ids:
                    continue
                setups = (
                    await db.execute(
                        select(BowlSetup)
                        .where(BowlSetup.creator_id.in_(followed_ids), BowlSetup.created_at >= since)
                        .order_by(BowlSetup.created_at.desc())
                        .limit(10)
                    )
                ).scalars().all()
                if not setups:
                    continue
                lines = "\n".join(f"- {setup.name}: /setups/{setup.id}" for setup in setups)
                message = EmailMessage()
                message["From"] = settings.SMTP_FROM_EMAIL
                message["To"] = user.email
                message["Subject"] = "ShishaGuid: новые забивки за неделю"
                message.set_content(f"Новые забивки от авторов, на которых вы подписаны:\n\n{lines}")
                try:
                    client.send_message(message)
                except Exception:
                    logger.exception("Failed to send weekly digest to %s", user.email)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
