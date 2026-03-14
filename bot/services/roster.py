from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Faculty, Group, Student
from bot.utils.names import normalize_group_name


async def get_or_create_faculty(session: AsyncSession, name: str) -> Faculty:
    result = await session.execute(select(Faculty).where(Faculty.name == name))
    faculty = result.scalar_one_or_none()
    if faculty:
        return faculty
    faculty = Faculty(name=name)
    session.add(faculty)
    await session.commit()
    await session.refresh(faculty)
    return faculty


async def get_or_create_group(session: AsyncSession, name: str, faculty_id: int) -> Group:
    normalized_name = normalize_group_name(name)
    result = await session.execute(select(Group).where(func.upper(Group.name) == normalized_name))
    group = result.scalar_one_or_none()
    if group:
        updated = False
        if group.name != normalized_name:
            group.name = normalized_name
            updated = True
        if group.faculty_id != faculty_id:
            group.faculty_id = faculty_id
            updated = True
        if updated:
            await session.commit()
            await session.refresh(group)
        return group
    group = Group(name=normalized_name, faculty_id=faculty_id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def add_students_to_group(
    session: AsyncSession,
    group_id: int,
    students: list[tuple[str, str, str | None]],
) -> int:
    count = 0
    for last, first, middle in students:
        session.add(Student(last_name=last, first_name=first, middle_name=middle, group_id=group_id))
        count += 1
    await session.commit()
    return count
