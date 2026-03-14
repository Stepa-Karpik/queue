from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Student, Group
from bot.utils.names import normalize_compare_text, split_full_name


async def find_students_by_last_name(session: AsyncSession, last_name: str) -> list[Student]:
    last_name = normalize_compare_text(last_name).split(" ")[0].lower()
    stmt = select(Student).where(func.replace(func.lower(Student.last_name), "ё", "е") == last_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_student_by_full_name(session: AsyncSession, full_name: str) -> list[Student]:
    last, first, middle = split_full_name(full_name)
    last = normalize_compare_text(last).lower()
    first = normalize_compare_text(first).lower()
    stmt = select(Student).where(
        func.replace(func.lower(Student.last_name), "ё", "е") == last,
        func.replace(func.lower(Student.first_name), "ё", "е") == first,
    )
    if middle:
        stmt = stmt.where(func.replace(func.lower(Student.middle_name), "ё", "е") == normalize_compare_text(middle).lower())
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
