import asyncio
import logging

import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from sqlalchemy.engine.url import make_url

from bot.handlers import start, profile, subjects, list_import, starosta, starosta_panel
from bot.middlewares.db import DbSessionMiddleware
from bot.utils.config import settings
from bot.utils.db import engine, Base


async def wait_for_db(retries: int = 10, delay: float = 1.5) -> None:
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as exc:  # noqa: BLE001 - surface final error
            last_exc = exc
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def ensure_database_exists() -> None:
    db_url = make_url(settings.database_url)
    target_db = db_url.database
    if not target_db:
        return

    conn = await asyncpg.connect(
        user=db_url.username,
        password=db_url.password,
        host=db_url.host or "localhost",
        port=db_url.port or 5432,
        database="postgres",
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", target_db)
        if not exists:
            await conn.execute(f"CREATE DATABASE {_quote_ident(target_db)}")
    finally:
        await conn.close()


async def on_startup() -> None:
    await ensure_database_exists()
    await wait_for_db()


def setup_logging() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(starosta_panel.router)
    dp.include_router(subjects.router)
    dp.include_router(list_import.router)
    dp.include_router(starosta.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
