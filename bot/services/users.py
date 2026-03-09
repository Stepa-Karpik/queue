from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import User, Role


async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(
        select(User).options(joinedload(User.student)).where(User.tg_id == tg_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    student_id: int | None,
    role: Role = Role.STUDENT,
) -> User:
    user = User(tg_id=tg_id, username=username, student_id=student_id, role=role.value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    student_id: int | None,
    role: Role = Role.STUDENT,
) -> User:
    user = await get_user_by_tg(session, tg_id)
    if user:
        return user
    return await create_user(session, tg_id, username, student_id, role)
