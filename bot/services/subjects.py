from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import GroupSubject, Subject, SubjectKind, SubjectWork


async def list_group_subjects(session: AsyncSession, group_id: int, kind: SubjectKind) -> list[GroupSubject]:
    stmt = (
        select(GroupSubject)
        .join(Subject)
        .options(joinedload(GroupSubject.subject))
        .where(GroupSubject.group_id == group_id, Subject.kind == kind.value, GroupSubject.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_group_subject(session: AsyncSession, group_subject_id: int) -> GroupSubject | None:
    result = await session.execute(
        select(GroupSubject)
        .options(joinedload(GroupSubject.subject), joinedload(GroupSubject.group))
        .where(GroupSubject.id == group_subject_id)
    )
    return result.scalar_one_or_none()


async def get_group_subject_by_name(session: AsyncSession, group_id: int, name: str) -> GroupSubject | None:
    stmt = (
        select(GroupSubject)
        .join(Subject)
        .options(joinedload(GroupSubject.subject))
        .where(GroupSubject.group_id == group_id, Subject.name == name, GroupSubject.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_active_work_numbers(session: AsyncSession, group_subject_id: int) -> list[int]:
    stmt = select(SubjectWork.number).where(
        SubjectWork.group_subject_id == group_subject_id,
        SubjectWork.is_active.is_(True),
    ).order_by(SubjectWork.number)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def create_subject_with_works(
    session: AsyncSession,
    group_id: int,
    name: str,
    kind: SubjectKind,
    work_count: int,
) -> GroupSubject:
    subject_result = await session.execute(select(Subject).where(Subject.name == name))
    subject = subject_result.scalar_one_or_none()
    if not subject:
        subject = Subject(name=name, kind=kind.value)
        session.add(subject)
        await session.flush()

    group_subject = await get_group_subject_by_name(session, group_id, name)
    if group_subject:
        return group_subject

    group_subject = GroupSubject(group_id=group_id, subject_id=subject.id)
    session.add(group_subject)
    await session.flush()
    for number in range(1, work_count + 1):
        session.add(SubjectWork(group_subject_id=group_subject.id, number=number))
    await session.commit()
    await session.refresh(group_subject)
    return group_subject


async def add_work_number(session: AsyncSession, group_subject_id: int) -> int:
    stmt = select(SubjectWork.number).where(SubjectWork.group_subject_id == group_subject_id).order_by(SubjectWork.number.desc())
    result = await session.execute(stmt)
    last = result.scalars().first() or 0
    new_number = last + 1
    session.add(SubjectWork(group_subject_id=group_subject_id, number=new_number))
    await session.commit()
    return new_number


async def deactivate_work_number(session: AsyncSession, group_subject_id: int, number: int) -> bool:
    stmt = select(SubjectWork).where(
        SubjectWork.group_subject_id == group_subject_id,
        SubjectWork.number == number,
        SubjectWork.is_active.is_(True),
    )
    result = await session.execute(stmt)
    work = result.scalar_one_or_none()
    if not work:
        return False
    work.is_active = False
    await session.commit()
    return True
