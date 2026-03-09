import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

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


async def on_startup() -> None:
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
