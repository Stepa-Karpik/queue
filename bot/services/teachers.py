from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import GroupTeacher, ScheduleEntry, ScheduleTemplate
from bot.utils.names import normalize_compare_text, normalize_name
from bot.utils.teacher_names import LESSON_TYPE_ORDER, normalize_teacher_name, normalize_teacher_records, render_teacher_records


def _compare_key(value: str) -> str:
    return normalize_compare_text(value).lower()


async def list_group_teachers(session: AsyncSession, group_id: int) -> list[GroupTeacher]:
    result = await session.execute(
        select(GroupTeacher)
        .where(GroupTeacher.group_id == group_id)
        .order_by(GroupTeacher.discipline, GroupTeacher.lesson_type, GroupTeacher.full_name)
    )
    return list(result.scalars().all())


async def list_group_teachers_for_slot(
    session: AsyncSession,
    group_id: int,
    discipline: str,
    lesson_type: str,
) -> list[GroupTeacher]:
    result = await session.execute(
        select(GroupTeacher)
        .where(
            GroupTeacher.group_id == group_id,
            GroupTeacher.discipline == normalize_name(discipline),
            GroupTeacher.lesson_type == (lesson_type or "").strip().lower(),
        )
        .order_by(GroupTeacher.full_name)
    )
    return list(result.scalars().all())


async def get_group_teacher(session: AsyncSession, teacher_id: int) -> GroupTeacher | None:
    result = await session.execute(select(GroupTeacher).where(GroupTeacher.id == teacher_id))
    return result.scalar_one_or_none()


async def list_schedule_teacher_slots(session: AsyncSession, group_id: int) -> list[tuple[str, str]]:
    result = await session.execute(
        select(ScheduleEntry.discipline_base, ScheduleEntry.lesson_type)
        .join(ScheduleTemplate, ScheduleTemplate.id == ScheduleEntry.template_id)
        .where(ScheduleTemplate.group_id == group_id)
    )
    unique_slots: dict[tuple[str, str], tuple[str, str]] = {}
    for discipline, lesson_type in result.all():
        cleaned_discipline = normalize_name(discipline or "")
        cleaned_lesson_type = (lesson_type or "").strip().lower()
        if not cleaned_discipline or not cleaned_lesson_type:
            continue
        unique_slots.setdefault((_compare_key(cleaned_discipline), cleaned_lesson_type), (cleaned_discipline, cleaned_lesson_type))

    return sorted(
        unique_slots.values(),
        key=lambda item: (_compare_key(item[0]), LESSON_TYPE_ORDER.get(item[1], LESSON_TYPE_ORDER["other"])),
    )


async def list_teacher_disciplines(session: AsyncSession, group_id: int) -> list[str]:
    slots = await list_schedule_teacher_slots(session, group_id)
    unique_disciplines: dict[str, str] = {}
    for discipline, _ in slots:
        unique_disciplines.setdefault(_compare_key(discipline), discipline)
    return sorted(unique_disciplines.values(), key=_compare_key)


async def list_teacher_lesson_types(session: AsyncSession, group_id: int, discipline: str) -> list[str]:
    cleaned_discipline = normalize_name(discipline or "")
    slots = await list_schedule_teacher_slots(session, group_id)
    lesson_types = {
        lesson_type
        for slot_discipline, lesson_type in slots
        if _compare_key(slot_discipline) == _compare_key(cleaned_discipline)
    }
    return sorted(lesson_types, key=lambda item: LESSON_TYPE_ORDER.get(item, LESSON_TYPE_ORDER["other"]))


async def add_group_teacher(
    session: AsyncSession,
    group_id: int,
    discipline: str,
    lesson_type: str,
    full_name: str,
) -> tuple[bool, str]:
    cleaned_discipline = normalize_name(discipline or "")
    cleaned_lesson_type = (lesson_type or "").strip().lower()
    cleaned_name = normalize_teacher_name(full_name)
    if not cleaned_discipline or not cleaned_lesson_type:
        return False, "Не удалось определить дисциплину или вид пары."
    if not cleaned_name:
        return False, "ФИО преподавателя не может быть пустым."

    teachers = await list_group_teachers_for_slot(session, group_id, cleaned_discipline, cleaned_lesson_type)
    if any(teacher.full_name == cleaned_name for teacher in teachers):
        return False, "Такой преподаватель уже есть в этом виде пары."

    session.add(
        GroupTeacher(
            group_id=group_id,
            discipline=cleaned_discipline,
            lesson_type=cleaned_lesson_type,
            full_name=cleaned_name,
        )
    )
    await session.commit()
    return True, "Преподаватель добавлен."


async def rename_group_teacher(session: AsyncSession, teacher_id: int, full_name: str) -> tuple[bool, str]:
    teacher = await get_group_teacher(session, teacher_id)
    if not teacher:
        return False, "Преподаватель не найден."

    cleaned_name = normalize_teacher_name(full_name)
    if not cleaned_name:
        return False, "ФИО преподавателя не может быть пустым."

    teachers = await list_group_teachers_for_slot(session, teacher.group_id, teacher.discipline, teacher.lesson_type)
    if any(item.id != teacher.id and item.full_name == cleaned_name for item in teachers):
        return False, "Такой преподаватель уже есть в этом виде пары."

    teacher.full_name = cleaned_name
    await session.commit()
    return True, "Данные преподавателя обновлены."


async def delete_group_teacher(session: AsyncSession, teacher_id: int) -> tuple[bool, str]:
    teacher = await get_group_teacher(session, teacher_id)
    if not teacher:
        return False, "Преподаватель не найден."
    await session.delete(teacher)
    await session.commit()
    return True, "Преподаватель удален."


async def list_schedule_teacher_records(session: AsyncSession, group_id: int) -> list[tuple[str, str, str]]:
    result = await session.execute(
        select(ScheduleEntry.discipline_base, ScheduleEntry.lesson_type, ScheduleEntry.teacher)
        .join(ScheduleTemplate, ScheduleTemplate.id == ScheduleEntry.template_id)
        .where(ScheduleTemplate.group_id == group_id)
    )
    entries = [(row[0], row[1], row[2]) for row in result.all() if row[0] and row[1] and row[2]]
    return normalize_teacher_records(entries)


async def replace_group_teachers_from_schedule(session: AsyncSession, group_id: int) -> tuple[bool, str]:
    teacher_records = await list_schedule_teacher_records(session, group_id)
    if not teacher_records:
        return False, "В расписании пока не отмечены преподаватели."

    await session.execute(delete(GroupTeacher).where(GroupTeacher.group_id == group_id))
    for discipline, lesson_type, full_name in teacher_records:
        session.add(
            GroupTeacher(
                group_id=group_id,
                discipline=discipline,
                lesson_type=lesson_type,
                full_name=full_name,
            )
        )
    await session.commit()
    return True, f"Список преподавателей обновлен: {len(teacher_records)}."


async def list_display_teacher_names(session: AsyncSession, group_id: int) -> list[str]:
    manual_teachers = await list_group_teachers(session, group_id)
    if manual_teachers:
        return render_teacher_records(
            [(teacher.discipline, teacher.lesson_type, teacher.full_name) for teacher in manual_teachers]
        )

    schedule_records = await list_schedule_teacher_records(session, group_id)
    return render_teacher_records(schedule_records)
