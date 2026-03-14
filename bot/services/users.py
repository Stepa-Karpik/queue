from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import Group, Role, ScheduleTemplate, Student, User
from bot.services.students import get_student_group
from bot.utils.config import settings


def is_admin_tg(tg_id: int) -> bool:
    return settings.admin_id is not None and tg_id == settings.admin_id


def is_admin_user(user: User | None) -> bool:
    return bool(user and is_admin_tg(user.tg_id))


def is_admin_mode(user: User | None) -> bool:
    return bool(user and is_admin_user(user) and user.is_admin_mode)


def is_starosta_user(user: User | None) -> bool:
    return bool(user and user.role == Role.STAROSTA.value)


async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(
        select(User)
        .options(
            joinedload(User.student),
            joinedload(User.admin_group).joinedload(Group.faculty),
        )
        .where(User.tg_id == tg_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_student(session: AsyncSession, student_id: int) -> User | None:
    result = await session.execute(select(User).where(User.student_id == student_id))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(
        select(User)
        .options(
            joinedload(User.student).joinedload(Student.group).joinedload(Group.faculty),
            joinedload(User.admin_group).joinedload(Group.faculty),
        )
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    student_id: int | None,
    role: Role = Role.STUDENT,
) -> User:
    user = User(
        tg_id=tg_id,
        username=username,
        student_id=student_id,
        role=role.value,
        is_admin_mode=False,
    )
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
        updated = False
        if user.username != username:
            user.username = username
            updated = True
        if user.student_id != student_id:
            user.student_id = student_id
            updated = True
        if user.role != role.value:
            user.role = role.value
            updated = True
        if updated:
            await session.commit()
            await session.refresh(user)
        return user
    return await create_user(session, tg_id, username, student_id, role)


async def set_admin_group(session: AsyncSession, user: User, group_id: int | None) -> User:
    user.admin_group_id = group_id
    await session.commit()
    await session.refresh(user)
    return user


async def set_admin_mode(session: AsyncSession, user: User, enabled: bool) -> User:
    user.is_admin_mode = bool(enabled and is_admin_user(user))
    await session.commit()
    await session.refresh(user)
    return user


async def get_effective_group(session: AsyncSession, user: User | None) -> Group | None:
    if not user:
        return None
    if is_admin_mode(user):
        if not user.admin_group_id:
            return None
        stmt = (
            select(Group)
            .options(joinedload(Group.faculty))
            .where(Group.id == user.admin_group_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    if not user.student_id:
        return None
    return await get_student_group(session, user.student_id)


async def delete_user_by_tg(session: AsyncSession, tg_id: int) -> bool:
    user = await get_user_by_tg(session, tg_id)
    if not user:
        return False
    await session.execute(
        update(ScheduleTemplate)
        .where(ScheduleTemplate.uploaded_by_user_id == user.id)
        .values(uploaded_by_user_id=None)
    )
    await session.delete(user)
    await session.commit()
    return True


async def list_registered_users(session: AsyncSession) -> list[User]:
    stmt = (
        select(User)
        .options(
            joinedload(User.student).joinedload(Student.group),
            joinedload(User.admin_group),
        )
        .order_by(User.role.desc(), User.username, User.tg_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_group_registered_users(session: AsyncSession, group_id: int, include_inactive: bool = False) -> list[User]:
    stmt = (
        select(User)
        .join(Student, Student.id == User.student_id)
        .options(joinedload(User.student))
        .where(Student.group_id == group_id)
    )
    if not include_inactive:
        stmt = stmt.where(Student.is_inactive.is_(False))
    result = await session.execute(stmt)
    return list(result.scalars().all())
