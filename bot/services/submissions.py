from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Submission, SubjectWork, Student


async def list_submitted_numbers(session: AsyncSession, student_id: int, group_subject_id: int) -> list[int]:
    stmt = select(Submission.work_number).where(
        Submission.student_id == student_id,
        Submission.group_subject_id == group_subject_id,
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def is_work_submitted(
    session: AsyncSession,
    student_id: int,
    group_subject_id: int,
    work_number: int,
) -> bool:
    stmt = select(Submission).where(
        Submission.student_id == student_id,
        Submission.group_subject_id == group_subject_id,
        Submission.work_number == work_number,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    return existing is not None


async def submit_work(
    session: AsyncSession,
    student_id: int,
    group_subject_id: int,
    work_number: int,
    score: int | None,
) -> bool:
    if await is_work_submitted(session, student_id, group_subject_id, work_number):
        return False
    session.add(
        Submission(
            student_id=student_id,
            group_subject_id=group_subject_id,
            work_number=work_number,
            score=score,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    return True


async def delete_submission(
    session: AsyncSession,
    student_id: int,
    group_subject_id: int,
    work_number: int,
) -> bool:
    stmt = select(Submission).where(
        Submission.student_id == student_id,
        Submission.group_subject_id == group_subject_id,
        Submission.work_number == work_number,
    )
    result = await session.execute(stmt)
    submission = result.scalar_one_or_none()
    if not submission:
        return False
    await session.delete(submission)
    await session.commit()
    return True


async def student_stats(session: AsyncSession, student_id: int, group_subject_id: int) -> tuple[int, float]:
    stmt = select(func.count(Submission.id), func.avg(Submission.score)).where(
        Submission.student_id == student_id,
        Submission.group_subject_id == group_subject_id,
    )
    result = await session.execute(stmt)
    count, avg = result.one()
    return int(count or 0), float(avg or 0.0)


async def list_group_students(session: AsyncSession, group_id: int) -> list[Student]:
    result = await session.execute(select(Student).where(Student.group_id == group_id).order_by(Student.last_name))
    return list(result.scalars().all())


async def total_active_works(session: AsyncSession, group_subject_id: int) -> int:
    stmt = select(func.count(SubjectWork.id)).where(
        SubjectWork.group_subject_id == group_subject_id,
        SubjectWork.is_active.is_(True),
    )
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_submission_details(session: AsyncSession, student_id: int, group_subject_id: int) -> list[Submission]:
    stmt = (
        select(Submission)
        .where(
            Submission.student_id == student_id,
            Submission.group_subject_id == group_subject_id,
        )
        .order_by(Submission.work_number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def submissions_map(session: AsyncSession, group_subject_id: int) -> dict[int, list[int]]:
    stmt = select(Submission.student_id, Submission.work_number).where(Submission.group_subject_id == group_subject_id)
    result = await session.execute(stmt)
    mapping: dict[int, list[int]] = {}
    for student_id, work_number in result.all():
        mapping.setdefault(student_id, []).append(work_number)
    return mapping
