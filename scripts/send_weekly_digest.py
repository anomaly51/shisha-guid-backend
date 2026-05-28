import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.email import send_email
from app.models.shisha import BowlSetup
from app.models.user import User, UserFollow


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    since = datetime.utcnow() - timedelta(days=7)

    async with session_factory() as db:
        users = (await db.execute(select(User).where(User.is_banned.is_(False)))).scalars().all()
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
            send_email(
                user.email,
                "ShishaGuid: новые забивки за неделю",
                f"Новые забивки от авторов, на которых вы подписаны:\n\n{lines}",
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
