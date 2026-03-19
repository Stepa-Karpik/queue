from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import (
    Faculty,
    Group,
    GroupSubject,
    GroupTeacher,
    ScheduleBinding,
    ScheduleEntry,
    ScheduleNotificationLog,
    ScheduleTemplate,
    SubjectWork,
    User,
    UserNotificationSubject,
)
from bot.services.admin_panel import delete_student_with_related, list_group_students_with_user
from bot.services.users import list_group_registered_users
from bot.utils.names import (
    get_group_validation_error_text,
    normalize_faculty_name,
    normalize_group_name,
    normalize_valid_group_name,
)


async def list_groups(session: AsyncSession) -> list[Group]:
    stmt = select(Group).options(joinedload(Group.faculty)).order_by(Group.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_group(session: AsyncSession, group_id: int) -> Group | None:
    stmt = select(Group).options(joinedload(Group.faculty)).where(Group.id == group_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_or_create_faculty(session: AsyncSession, name: str) -> Faculty:
    normalized_name = normalize_faculty_name(name)
    result = await session.execute(select(Faculty))
    faculties = list(result.scalars().all())
    faculty = next((item for item in faculties if normalize_faculty_name(item.name) == normalized_name), None)
    if faculty:
        if faculty.name != normalized_name:
            faculty.name = normalized_name
            await session.commit()
            await session.refresh(faculty)
        return faculty
    faculty = Faculty(name=normalized_name)
    session.add(faculty)
    await session.commit()
    await session.refresh(faculty)
    return faculty


async def create_group_with_faculty(session: AsyncSession, group_name: str, faculty_name: str) -> tuple[bool, str, Group | None]:
    normalized_group_name = normalize_valid_group_name(group_name)
    normalized_faculty_name = normalize_faculty_name(faculty_name)
    if not normalized_group_name:
        return False, get_group_validation_error_text(), None
    if not normalized_faculty_name:
        return False, "Факультет не может быть пустым.", None

    existing_result = await session.execute(select(Group).where(func.upper(Group.name) == normalized_group_name))
    if existing_result.scalar_one_or_none():
        return False, "Такая группа уже существует.", None

    faculty = await _get_or_create_faculty(session, normalized_faculty_name)
    group = Group(name=normalized_group_name, faculty_id=faculty.id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    group = await get_group(session, group.id)
    return True, "Группа добавлена.", group


async def update_group_name(session: AsyncSession, group_id: int, group_name: str) -> tuple[bool, str, Group | None]:
    group = await get_group(session, group_id)
    if not group:
        return False, "Группа не найдена.", None

    normalized_group_name = normalize_valid_group_name(group_name)
    if not normalized_group_name:
        return False, get_group_validation_error_text(), None

    duplicate_result = await session.execute(
        select(Group).where(func.upper(Group.name) == normalized_group_name, Group.id != group_id)
    )
    if duplicate_result.scalar_one_or_none():
        return False, "Такая группа уже существует.", None

    group.name = normalized_group_name
    await session.commit()
    group = await get_group(session, group_id)
    return True, "Название группы обновлено.", group


async def update_group_faculty(session: AsyncSession, group_id: int, faculty_name: str) -> tuple[bool, str, Group | None]:
    group = await get_group(session, group_id)
    if not group:
        return False, "Группа не найдена.", None

    normalized_faculty_name = normalize_faculty_name(faculty_name)
    if not normalized_faculty_name:
        return False, "Факультет не может быть пустым.", None

    faculty = await _get_or_create_faculty(session, normalized_faculty_name)
    group.faculty_id = faculty.id
    await session.commit()
    group = await get_group(session, group_id)
    return True, "Факультет группы обновлен.", group


async def delete_group_with_related(session: AsyncSession, group_id: int) -> tuple[bool, str, list[int]]:
    group = await get_group(session, group_id)
    if not group:
        return False, "Группа не найдена.", []

    group_name = normalize_group_name(group.name)
    registered_users = await list_group_registered_users(session, group_id, include_inactive=True)
    notify_tg_ids = [user.tg_id for user in registered_users]

    students = await list_group_students_with_user(session, group_id)
    for student in students:
        await delete_student_with_related(session, student.id)

    subject_ids_result = await session.execute(select(GroupSubject.id).where(GroupSubject.group_id == group_id))
    group_subject_ids = [row[0] for row in subject_ids_result.all()]

    await session.execute(update(User).where(User.admin_group_id == group_id).values(admin_group_id=None))
    await session.execute(delete(GroupTeacher).where(GroupTeacher.group_id == group_id))
    await session.execute(delete(ScheduleNotificationLog).where(ScheduleNotificationLog.group_id == group_id))
    await session.execute(delete(ScheduleBinding).where(ScheduleBinding.group_id == group_id))

    template_ids_result = await session.execute(select(ScheduleTemplate.id).where(ScheduleTemplate.group_id == group_id))
    template_ids = [row[0] for row in template_ids_result.all()]
    if template_ids:
        await session.execute(delete(ScheduleEntry).where(ScheduleEntry.template_id.in_(template_ids)))
    await session.execute(delete(ScheduleTemplate).where(ScheduleTemplate.group_id == group_id))

    if group_subject_ids:
        await session.execute(delete(UserNotificationSubject).where(UserNotificationSubject.group_subject_id.in_(group_subject_ids)))
        await session.execute(delete(SubjectWork).where(SubjectWork.group_subject_id.in_(group_subject_ids)))
        await session.execute(delete(GroupSubject).where(GroupSubject.id.in_(group_subject_ids)))

    await session.execute(delete(Group).where(Group.id == group_id))
    await session.commit()
    return True, group_name, notify_tg_ids
