import asyncio

import app.models  # noqa: F401
from app.core.database import engine
from app.core.startup import bootstrap_database


async def _bootstrap() -> None:
    try:
        await bootstrap_database(engine)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_bootstrap())


if __name__ == "__main__":
    main()
