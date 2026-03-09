from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Student, Group
from bot.utils.names import normalize_name, split_full_name


async def find_students_by_last_name(session: AsyncSession, last_name: str) -> list[Student]:
    last_name = normalize_name(last_name).split(" ")[0]
    stmt = select(Student).where(func.lower(Student.last_name) == last_name.lower())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_student_by_full_name(session: AsyncSession, full_name: str) -> list[Student]:
    last, first, middle = split_full_name(full_name)
    stmt = select(Student).where(
        func.lower(Student.last_name) == last.lower(),
        func.lower(Student.first_name) == first.lower(),
    )
    if middle:
        stmt = stmt.where(func.lower(Student.middle_name) == middle.lower())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_student_group(session: AsyncSession, student_id: int) -> Group | None:
    stmt = (
        select(Group)
        .join(Student)
        .options(joinedload(Group.faculty))
        .where(Student.id == student_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
