from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import GroupSubject, Student, Submission, SubjectWork
from bot.utils.names import format_full_name, format_short_name


class PriorityResult(dict):
    student_id: int
    full_name: str
    short_name: str
    priority: float
    is_inactive: bool
    completed: int
    total: int
    avg_score: float
    scored_count: int
    last_submission_at: datetime | None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_priority(
    total: int,
    completed: int,
    avg_score: float,
    last_submission_at: datetime | None,
) -> float:
    if total <= 0:
        return 0.0

    remaining = total - completed
    completion_ratio = completed / total
    remaining_ratio = remaining / total

    if remaining == 0:
        return 0.0

    # 1) Remaining bonus: if 1-2 works left, priority jumps
    if remaining <= 2:
        remaining_bonus = 2.0 + (2 - remaining) * 0.75
    else:
        remaining_bonus = 1.0

    # 2) Inactivity factor: longer silence -> higher priority (cap 2.0)
    if last_submission_at:
        last_dt = _ensure_utc(last_submission_at)
        delta_days = (datetime.now(timezone.utc) - last_dt).days
    else:
        delta_days = 60
    inactivity_factor = min(2.0, 1.0 + min(delta_days, 30) / 30)

    # 3) Low progress penalty: if student almost submits nothing, priority drops
    low_progress_penalty = 0.5 + completion_ratio  # from 0.5 to 1.5

    # 4) Average score modifier: modest influence
    avg_score_modifier = 0.8 + (max(min(avg_score, 100), 0) / 100) * 0.4  # 0.8..1.2

    # 5) Remaining ratio emphasizes those who still have work to do
    priority = remaining_ratio * remaining_bonus * inactivity_factor * low_progress_penalty * avg_score_modifier

    # Normalize slightly to keep values in a predictable band
    return round(priority, 4)


async def get_priority_list(session: AsyncSession, group_subject_id: int) -> list[PriorityResult]:
    gs = await session.get(GroupSubject, group_subject_id)
    if not gs:
        return []

    total_stmt = select(func.count(SubjectWork.id)).where(
        SubjectWork.group_subject_id == group_subject_id,
        SubjectWork.is_active.is_(True),
    )
    total = int((await session.execute(total_stmt)).scalar_one() or 0)

    submissions_subq = (
        select(
            Submission.student_id.label("student_id"),
            func.count(Submission.id).label("completed"),
            func.avg(Submission.score).label("avg_score"),
            func.count(Submission.score).label("scored_count"),
            func.max(Submission.submitted_at).label("last_submission_at"),
        )
        .where(Submission.group_subject_id == group_subject_id)
        .group_by(Submission.student_id)
        .subquery()
    )

    stmt = (
        select(
            Student.id,
            Student.last_name,
            Student.first_name,
            Student.middle_name,
            Student.is_inactive,
            submissions_subq.c.completed,
            submissions_subq.c.avg_score,
            submissions_subq.c.scored_count,
            submissions_subq.c.last_submission_at,
        )
        .select_from(
            outerjoin(Student, submissions_subq, Student.id == submissions_subq.c.student_id)
        )
        .where(Student.group_id == gs.group_id)
        .order_by(Student.last_name)
    )

    result = await session.execute(stmt)
    items: list[PriorityResult] = []
    for row in result.all():
        completed = int(row.completed or 0)
        avg_score = float(row.avg_score or 0.0)
        scored_count = int(row.scored_count or 0)
        last_submission_at = row.last_submission_at
        full_name = format_full_name(row.last_name, row.first_name, row.middle_name)
        short_name = format_short_name(row.last_name, row.first_name, row.middle_name)
        priority = 0.0 if row.is_inactive else compute_priority(total, completed, avg_score, last_submission_at)
        items.append(
            PriorityResult(
                student_id=row.id,
                full_name=full_name,
                short_name=short_name,
                priority=priority,
                is_inactive=bool(row.is_inactive),
                completed=completed,
                total=total,
                avg_score=avg_score,
                scored_count=scored_count,
                last_submission_at=last_submission_at,
            )
        )

    items.sort(key=lambda x: (x["is_inactive"], -x["priority"], x["short_name"]))
    return items
