import asyncio
import contextlib
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from bot.handlers import admin, group_list, list_import, management, profile, schedule, start, starosta, subjects
from bot.middlewares.db import DbSessionMiddleware
from bot.services.preferences import list_manual_notification_subject_ids_map
from bot.services.priority import get_priority_list
from bot.services.schedule import get_upcoming_bound_entries, mark_notification_sent, was_notification_sent
from bot.services.users import list_group_registered_users
from bot.utils.config import settings
from bot.utils.db import AsyncSessionLocal, Base, engine
from bot.utils.notification_filters import get_students_with_pending_works
from bot.utils.user_settings import should_send_subject_notification

MSK = ZoneInfo("Europe/Moscow")


async def wait_for_db(retries: int = 10, delay: float = 1.5) -> None:
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await ensure_schema_updates()
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc


async def ensure_schema_updates() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS is_inactive BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_group_id INTEGER"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin_mode BOOLEAN NOT NULL DEFAULT FALSE"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS notification_mode VARCHAR(16) NOT NULL DEFAULT 'auto'"))
        await conn.execute(text("ALTER TABLE group_teachers ADD COLUMN IF NOT EXISTS discipline VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE group_teachers ADD COLUMN IF NOT EXISTS lesson_type VARCHAR(16)"))
        await conn.execute(text("DELETE FROM group_teachers WHERE discipline IS NULL OR lesson_type IS NULL"))
        await conn.execute(
            text(
                """
                DELETE FROM group_teachers AS duplicate
                USING group_teachers AS original
                WHERE duplicate.id > original.id
                  AND duplicate.group_id = original.group_id
                  AND duplicate.discipline = original.discipline
                  AND duplicate.lesson_type = original.lesson_type
                  AND duplicate.full_name = original.full_name
                """
            )
        )
        await conn.execute(text("ALTER TABLE group_teachers ALTER COLUMN discipline SET NOT NULL"))
        await conn.execute(text("ALTER TABLE group_teachers ALTER COLUMN lesson_type SET NOT NULL"))
        await conn.execute(text("ALTER TABLE group_teachers DROP CONSTRAINT IF EXISTS uq_group_teacher"))
        await conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'uq_group_teacher_slot'
                    ) THEN
                        ALTER TABLE group_teachers
                        ADD CONSTRAINT uq_group_teacher_slot UNIQUE (group_id, discipline, lesson_type, full_name);
                    END IF;
                END$$;
                """
            )
        )
        await conn.execute(text("UPDATE users SET role = 'student', is_admin_mode = FALSE WHERE role = 'admin'"))


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


def build_priority_notification_text(subject_name: str, pair_start: datetime, items: list[dict]) -> str:
    lines = [
        f"⏰ Через 5 минут начинается занятие по дисциплине «{subject_name}».",
        f"Пара стартует в {pair_start.astimezone(MSK).strftime('%H:%M')} МСК.",
        "",
        "Очередность сдачи:",
    ]
    active_index = 1
    for item in items:
        if item["is_inactive"]:
            lines.append(f"🟥 {item['short_name']} — неактивен")
            continue
        lines.append(f"{active_index}. {item['short_name']} — {item['completed']}/{item['total']}")
        active_index += 1
    if active_index == 1:
        lines.append("На данный момент все активные студенты уже закрыли работы по дисциплине.")
    return "\n".join(lines)


async def notification_loop(bot: Bot) -> None:
    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now(MSK)
                upcoming = await get_upcoming_bound_entries(session, now)
                for entry, binding in upcoming:
                    already_sent = await was_notification_sent(session, entry.group_id, entry.discipline_key, entry.pair_start_at)
                    if already_sent:
                        continue

                    priority_items = await get_priority_list(session, binding.group_subject_id)
                    if not priority_items:
                        continue

                    pending_student_ids = get_students_with_pending_works(priority_items)
                    users = await list_group_registered_users(session, entry.group_id)
                    manual_subject_ids_map = await list_manual_notification_subject_ids_map(
                        session,
                        [user.id for user in users],
                    )

                    recipient_users = []
                    for user in users:
                        if not user.student_id:
                            continue
                        should_send = should_send_subject_notification(
                            user.notification_mode,
                            group_subject_id=binding.group_subject_id,
                            has_pending_work=user.student_id in pending_student_ids,
                            manual_subject_ids=manual_subject_ids_map.get(user.id, set()),
                        )
                        if should_send:
                            recipient_users.append(user)

                    if not recipient_users:
                        continue

                    text_message = build_priority_notification_text(
                        binding.group_subject.subject.name,
                        entry.pair_start_at,
                        [item for item in priority_items if item["student_id"] in pending_student_ids],
                    )

                    for user in recipient_users:
                        try:
                            await bot.send_message(user.tg_id, text_message)
                        except Exception:  # noqa: BLE001
                            logging.exception("Failed to send notification to tg_id=%s", user.tg_id)

                    await mark_notification_sent(session, entry.group_id, entry.discipline_key, entry.pair_start_at, text_message)
        except Exception:  # noqa: BLE001
            logging.exception("Notification loop iteration failed")

        await asyncio.sleep(60)


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(group_list.router)
    dp.include_router(schedule.router)
    dp.include_router(admin.router)
    dp.include_router(management.router)
    dp.include_router(subjects.router)
    dp.include_router(list_import.router)
    dp.include_router(starosta.router)

    notification_task = asyncio.create_task(notification_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        notification_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await notification_task


if __name__ == "__main__":
    asyncio.run(main())
