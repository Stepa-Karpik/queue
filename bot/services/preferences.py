from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import NotificationMode, User, UserNotificationSubject


async def set_user_notification_mode(session: AsyncSession, user: User, mode: str) -> User:
    user.notification_mode = mode
    await session.commit()
    await session.refresh(user)
    return user


async def list_user_manual_notification_subject_ids(session: AsyncSession, user_id: int) -> set[int]:
    result = await session.execute(
        select(UserNotificationSubject.group_subject_id).where(UserNotificationSubject.user_id == user_id)
    )
    return {row[0] for row in result.all()}


async def list_manual_notification_subject_ids_map(session: AsyncSession, user_ids: list[int]) -> dict[int, set[int]]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(UserNotificationSubject.user_id, UserNotificationSubject.group_subject_id).where(
            UserNotificationSubject.user_id.in_(user_ids)
        )
    )
    items: dict[int, set[int]] = defaultdict(set)
    for user_id, group_subject_id in result.all():
        items[int(user_id)].add(int(group_subject_id))
    return dict(items)


async def toggle_user_manual_notification_subject(session: AsyncSession, user_id: int, group_subject_id: int) -> set[int]:
    existing = await session.execute(
        select(UserNotificationSubject).where(
            UserNotificationSubject.user_id == user_id,
            UserNotificationSubject.group_subject_id == group_subject_id,
        )
    )
    link = existing.scalar_one_or_none()
    if link:
        await session.delete(link)
    else:
        session.add(UserNotificationSubject(user_id=user_id, group_subject_id=group_subject_id))
    await session.commit()
    return await list_user_manual_notification_subject_ids(session, user_id)


async def clear_user_manual_notification_subjects(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(UserNotificationSubject).where(UserNotificationSubject.user_id == user_id))
    await session.commit()


async def clear_user_manual_notification_subjects_for_group_change(session: AsyncSession, user_id: int) -> None:
    await clear_user_manual_notification_subjects(session, user_id)


def all_notification_modes() -> list[str]:
    return [
        NotificationMode.ENABLED.value,
        NotificationMode.DISABLED.value,
        NotificationMode.AUTO.value,
        NotificationMode.MANUAL.value,
    ]
