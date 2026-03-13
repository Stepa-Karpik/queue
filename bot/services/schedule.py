from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo
import re

import openpyxl
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import (
    Group,
    GroupSubject,
    ScheduleBinding,
    ScheduleEntry,
    ScheduleLessonType,
    ScheduleNotificationLog,
    ScheduleTemplate,
    ScheduleWeekType,
    SubjectKind,
)
from bot.utils.names import normalize_name

MSK = ZoneInfo("Europe/Moscow")
DAY_LABELS = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среду",
    3: "Четверг",
    4: "Пятницу",
    5: "Субботу",
}
PAIR_NUMBERS = {
    "08:30": 1,
    "10:15": 2,
    "12:00": 3,
    "14:15": 4,
    "16:00": 5,
    "17:45": 6,
    "19:30": 7,
}


@dataclass(slots=True)
class ParsedScheduleEntry:
    weekday: int
    lesson_date: date
    pair_number: int
    time_from: time
    time_to: time
    lesson_type: str
    discipline: str
    discipline_base: str
    discipline_key: str
    subgroup: str | None
    teacher: str | None
    room: str | None


@dataclass(slots=True)
class RenderedScheduleEntry:
    group_id: int
    event_date: date
    pair_start_at: datetime
    pair_end_at: datetime
    pair_number: int
    lesson_type: str
    discipline: str
    discipline_base: str
    discipline_key: str
    teacher: str | None
    room: str | None


def _parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    raise ValueError("Неверный формат даты в расписании.")


def _parse_time(value) -> time:
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    if isinstance(value, str):
        cleaned = value.strip().replace(".", ":")
        return datetime.strptime(cleaned, "%H:%M").time()
    raise ValueError("Неверный формат времени в расписании.")


def _pair_number(time_from: time) -> int:
    return PAIR_NUMBERS.get(time_from.strftime("%H:%M"), 0) or 1


def _lesson_type_from_token(token: str) -> str:
    cleaned = token.strip().lower().replace(".", "")
    if cleaned.startswith("лаб"):
        return ScheduleLessonType.LAB.value
    if cleaned.startswith("пр"):
        return ScheduleLessonType.PRACTICE.value
    if cleaned.startswith("лек"):
        return ScheduleLessonType.LECTURE.value
    return ScheduleLessonType.OTHER.value


def lesson_type_label(lesson_type: str) -> str:
    return {
        ScheduleLessonType.LAB.value: "лаб",
        ScheduleLessonType.PRACTICE.value: "пр",
        ScheduleLessonType.LECTURE.value: "лек",
    }.get(lesson_type, "зан")


def _normalize_subject_base(value: str) -> tuple[str, str | None]:
    cleaned = normalize_name(value)
    subgroup_match = re.search(r",\s*п/?г\s*([0-9A-Za-zА-Яа-я-]+)\s*$", cleaned, flags=re.IGNORECASE)
    subgroup = None
    if subgroup_match:
        subgroup = subgroup_match.group(0).lstrip(", ").strip()
        cleaned = cleaned[: subgroup_match.start()].rstrip(", ").strip()
    return cleaned, subgroup


def build_discipline_key(lesson_type: str, discipline_base: str) -> str:
    normalized = normalize_name(discipline_base).lower()
    return f"{lesson_type}:{normalized}"


def parse_schedule_excel(data: bytes) -> tuple[str | None, date, list[ParsedScheduleEntry]]:
    workbook = openpyxl.load_workbook(BytesIO(data), data_only=True)
    sheet = workbook.active

    entries: list[ParsedScheduleEntry] = []
    group_name: str | None = None
    week_dates: list[date] = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 8:
            continue
        if not row[1] or not row[2] or not row[3] or not row[4]:
            continue

        lesson_date = _parse_date(row[1])
        time_from = _parse_time(row[2])
        time_to = _parse_time(row[3])
        raw_discipline = normalize_name(str(row[4]))
        if not raw_discipline:
            continue

        parts = raw_discipline.split(" ", 1)
        type_token = parts[0]
        lesson_type = _lesson_type_from_token(type_token)
        discipline_without_type = parts[1].strip() if len(parts) > 1 else raw_discipline
        discipline_base, subgroup = _normalize_subject_base(discipline_without_type)
        discipline_key = build_discipline_key(lesson_type, discipline_base)
        group_name = normalize_name(str(row[7])) if row[7] else group_name

        entries.append(
            ParsedScheduleEntry(
                weekday=lesson_date.weekday(),
                lesson_date=lesson_date,
                pair_number=_pair_number(time_from),
                time_from=time_from,
                time_to=time_to,
                lesson_type=lesson_type,
                discipline=discipline_without_type,
                discipline_base=discipline_base,
                discipline_key=discipline_key,
                subgroup=subgroup,
                teacher=normalize_name(str(row[5])) if row[5] else None,
                room=normalize_name(str(row[6])) if row[6] else None,
            )
        )
        week_dates.append(lesson_date)

    if not entries or not week_dates:
        raise ValueError("В файле не найдено расписание.")

    week_start = min(week_dates)
    week_start = week_start - timedelta(days=week_start.weekday())
    entries.sort(key=lambda item: (item.weekday, item.time_from, item.discipline))
    return group_name, week_start, entries


async def upsert_schedule_template(
    session: AsyncSession,
    group_id: int,
    week_type: ScheduleWeekType,
    week_start: date,
    entries: list[ParsedScheduleEntry],
    uploaded_by_user_id: int | None = None,
) -> ScheduleTemplate:
    stmt = select(ScheduleTemplate).where(
        ScheduleTemplate.group_id == group_id,
        ScheduleTemplate.week_type == week_type.value,
    )
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        template = ScheduleTemplate(
            group_id=group_id,
            week_type=week_type.value,
            week_start=week_start,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        session.add(template)
        await session.flush()
    else:
        template.week_start = week_start
        template.uploaded_by_user_id = uploaded_by_user_id
        await session.execute(delete(ScheduleEntry).where(ScheduleEntry.template_id == template.id))
        await session.flush()

    for entry in entries:
        session.add(
            ScheduleEntry(
                template_id=template.id,
                weekday=entry.weekday,
                lesson_date=entry.lesson_date,
                pair_number=entry.pair_number,
                time_from=entry.time_from,
                time_to=entry.time_to,
                lesson_type=entry.lesson_type,
                discipline=entry.discipline,
                discipline_base=entry.discipline_base,
                discipline_key=entry.discipline_key,
                subgroup=entry.subgroup,
                teacher=entry.teacher,
                room=entry.room,
            )
        )

    await session.commit()
    await session.refresh(template)
    return template


async def get_schedule_templates(session: AsyncSession, group_id: int) -> dict[str, ScheduleTemplate]:
    stmt = (
        select(ScheduleTemplate)
        .options(joinedload(ScheduleTemplate.entries))
        .where(ScheduleTemplate.group_id == group_id)
    )
    result = await session.execute(stmt)
    templates = list(result.scalars().unique().all())
    return {template.week_type: template for template in templates}


async def has_full_schedule(session: AsyncSession, group_id: int) -> bool:
    templates = await get_schedule_templates(session, group_id)
    return (
        ScheduleWeekType.LOWER.value in templates
        and ScheduleWeekType.UPPER.value in templates
        and bool(templates[ScheduleWeekType.LOWER.value].entries)
        and bool(templates[ScheduleWeekType.UPPER.value].entries)
    )


def current_reference_date(now: datetime | None = None) -> date:
    now = now.astimezone(MSK) if now else datetime.now(MSK)
    if now.weekday() == 6:
        now = now + timedelta(days=1)
    return now.date()


def week_start_for_date(target_date: date) -> date:
    return target_date - timedelta(days=target_date.weekday())


def resolve_week_type(templates: dict[str, ScheduleTemplate], target_week_start: date) -> str | None:
    lower = templates.get(ScheduleWeekType.LOWER.value)
    upper = templates.get(ScheduleWeekType.UPPER.value)

    if lower:
        weeks_diff = abs((target_week_start - lower.week_start).days) // 7
        if weeks_diff % 2 == 0:
            return lower.week_type
        if upper:
            return upper.week_type
        return None

    if upper:
        weeks_diff = abs((target_week_start - upper.week_start).days) // 7
        if weeks_diff % 2 == 0:
            return upper.week_type
        return None

    return None


async def render_week_entries(
    session: AsyncSession,
    group_id: int,
    reference_date: date | None = None,
) -> tuple[date, list[RenderedScheduleEntry]]:
    templates = await get_schedule_templates(session, group_id)
    if not templates:
        return week_start_for_date(current_reference_date()), []

    target_date = reference_date or current_reference_date()
    target_week_start = week_start_for_date(target_date)
    week_type = resolve_week_type(templates, target_week_start)
    if not week_type:
        return target_week_start, []

    template = templates.get(week_type)
    if not template:
        return target_week_start, []

    rendered: list[RenderedScheduleEntry] = []
    for entry in sorted(template.entries, key=lambda item: (item.weekday, item.time_from, item.discipline)):
        event_date = target_week_start + timedelta(days=entry.weekday)
        pair_start_at = datetime.combine(event_date, entry.time_from, tzinfo=MSK)
        pair_end_at = datetime.combine(event_date, entry.time_to, tzinfo=MSK)
        rendered.append(
            RenderedScheduleEntry(
                group_id=group_id,
                event_date=event_date,
                pair_start_at=pair_start_at,
                pair_end_at=pair_end_at,
                pair_number=entry.pair_number,
                lesson_type=entry.lesson_type,
                discipline=entry.discipline,
                discipline_base=entry.discipline_base,
                discipline_key=entry.discipline_key,
                teacher=entry.teacher,
                room=entry.room,
            )
        )
    return target_week_start, rendered


def format_schedule_text(entries: list[RenderedScheduleEntry]) -> str:
    if not entries:
        return "Расписание пока не получено."

    lines: list[str] = []
    grouped: dict[date, list[RenderedScheduleEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.event_date, []).append(entry)

    for current_date, day_entries in grouped.items():
        day_label = DAY_LABELS.get(current_date.weekday(), current_date.strftime("%A"))
        lines.append(f"📆 Расписание на {day_label}, {current_date.strftime('%d/%m/%y')}:")
        lines.append("")
        for entry in day_entries:
            lines.append(f"{entry.pair_number}. {lesson_type_label(entry.lesson_type)} {entry.discipline}")
            lines.append(f" 🕗 {entry.pair_start_at.strftime('%H:%M')} - {entry.pair_end_at.strftime('%H:%M')} ")
            lines.append(f" 🚪 {entry.room or '—'} ")
            lines.append(f" 👤 {entry.teacher or '—'}")
            lines.append("")
        lines.append("")
    return "\n".join(lines).strip()


async def list_bindable_subjects(session: AsyncSession, group_id: int) -> list[dict[str, str]]:
    templates = await get_schedule_templates(session, group_id)
    seen: dict[str, dict[str, str]] = {}
    for template in templates.values():
        for entry in template.entries:
            if entry.lesson_type not in {ScheduleLessonType.LAB.value, ScheduleLessonType.PRACTICE.value}:
                continue
            if entry.discipline_key not in seen:
                seen[entry.discipline_key] = {
                    "discipline_key": entry.discipline_key,
                    "discipline_label": f"{lesson_type_label(entry.lesson_type)} {entry.discipline_base}",
                    "lesson_type": entry.lesson_type,
                }
    return sorted(seen.values(), key=lambda item: item["discipline_label"])


async def list_schedule_bindings(session: AsyncSession, group_id: int) -> list[ScheduleBinding]:
    stmt = (
        select(ScheduleBinding)
        .options(joinedload(ScheduleBinding.group_subject).joinedload(GroupSubject.subject))
        .where(ScheduleBinding.group_id == group_id)
        .order_by(ScheduleBinding.discipline_label)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_schedule_binding(
    session: AsyncSession,
    group_id: int,
    discipline_key: str,
    discipline_label: str,
    lesson_type: str,
    group_subject_id: int,
) -> ScheduleBinding:
    stmt = select(ScheduleBinding).where(
        ScheduleBinding.group_id == group_id,
        ScheduleBinding.discipline_key == discipline_key,
    )
    result = await session.execute(stmt)
    binding = result.scalar_one_or_none()
    if not binding:
        binding = ScheduleBinding(
            group_id=group_id,
            discipline_key=discipline_key,
            discipline_label=discipline_label,
            lesson_type=lesson_type,
            group_subject_id=group_subject_id,
        )
        session.add(binding)
    else:
        binding.discipline_label = discipline_label
        binding.lesson_type = lesson_type
        binding.group_subject_id = group_subject_id

    await session.commit()
    await session.refresh(binding)
    return binding


async def get_groups_with_schedule_bindings(session: AsyncSession) -> list[Group]:
    stmt = (
        select(Group)
        .join(ScheduleTemplate, ScheduleTemplate.group_id == Group.id)
        .join(ScheduleBinding, ScheduleBinding.group_id == Group.id)
        .options(joinedload(Group.faculty))
        .distinct()
        .order_by(Group.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_upcoming_bound_entries(
    session: AsyncSession,
    now: datetime,
    horizon_minutes: int = 5,
) -> list[tuple[RenderedScheduleEntry, ScheduleBinding]]:
    groups = await get_groups_with_schedule_bindings(session)
    upcoming: list[tuple[RenderedScheduleEntry, ScheduleBinding]] = []
    horizon = now + timedelta(minutes=horizon_minutes)

    for group in groups:
        _, entries = await render_week_entries(session, group.id, reference_date=now.date())
        bindings = {binding.discipline_key: binding for binding in await list_schedule_bindings(session, group.id)}
        for entry in entries:
            if entry.discipline_key not in bindings:
                continue
            if not (now <= entry.pair_start_at <= horizon):
                continue
            upcoming.append((entry, bindings[entry.discipline_key]))
    return upcoming


async def was_notification_sent(
    session: AsyncSession,
    group_id: int,
    discipline_key: str,
    pair_start_at: datetime,
) -> bool:
    stmt = select(ScheduleNotificationLog).where(
        ScheduleNotificationLog.group_id == group_id,
        ScheduleNotificationLog.discipline_key == discipline_key,
        ScheduleNotificationLog.pair_start_at == pair_start_at,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_notification_sent(
    session: AsyncSession,
    group_id: int,
    discipline_key: str,
    pair_start_at: datetime,
    message_text: str,
) -> None:
    session.add(
        ScheduleNotificationLog(
            group_id=group_id,
            discipline_key=discipline_key,
            pair_start_at=pair_start_at,
            message_text=message_text,
        )
    )
    await session.commit()


def subject_kind_from_schedule_lesson(lesson_type: str) -> SubjectKind | None:
    if lesson_type == ScheduleLessonType.LAB.value:
        return SubjectKind.LAB
    if lesson_type == ScheduleLessonType.PRACTICE.value:
        return SubjectKind.PRACTICE
    return None
