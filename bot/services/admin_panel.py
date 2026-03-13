from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import GroupSubject, Role, ScheduleTemplate, Student, Subject, SubjectKind, Submission, User
from bot.utils.names import normalize_name


async def list_group_subjects_all(session: AsyncSession, group_id: int) -> list[GroupSubject]:
    stmt = (
        select(GroupSubject)
        .join(Subject, Subject.id == GroupSubject.subject_id)
        .options(joinedload(GroupSubject.subject))
        .where(GroupSubject.group_id == group_id, GroupSubject.is_active.is_(True))
        .order_by(Subject.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_group_subject_active(session: AsyncSession, group_subject_id: int) -> GroupSubject | None:
    stmt = (
        select(GroupSubject)
        .options(joinedload(GroupSubject.subject), joinedload(GroupSubject.group))
        .where(GroupSubject.id == group_subject_id, GroupSubject.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def rename_group_subject(session: AsyncSession, group_subject_id: int, new_name: str) -> tuple[bool, str]:
    gs = await get_group_subject_active(session, group_subject_id)
    if not gs:
        return False, "Дисциплина не найдена."

    cleaned_name = normalize_name(new_name)
    if not cleaned_name:
        return False, "Название не может быть пустым."

    same_name_subject_result = await session.execute(select(Subject).where(Subject.name == cleaned_name))
    target_subject = same_name_subject_result.scalar_one_or_none()
    if target_subject:
        existing_link_result = await session.execute(
            select(GroupSubject).where(
                GroupSubject.group_id == gs.group_id,
                GroupSubject.subject_id == target_subject.id,
                GroupSubject.is_active.is_(True),
                GroupSubject.id != gs.id,
            )
        )
        duplicate = existing_link_result.scalar_one_or_none()
        if duplicate:
            return False, "В этой группе уже есть дисциплина с таким названием."
        gs.subject_id = target_subject.id
    else:
        new_subject = Subject(name=cleaned_name, kind=gs.subject.kind)
        session.add(new_subject)
        await session.flush()
        gs.subject_id = new_subject.id

    await session.commit()
    return True, "Название дисциплины обновлено."


async def set_group_subject_kind(session: AsyncSession, group_subject_id: int, kind: SubjectKind) -> tuple[bool, str]:
    gs = await get_group_subject_active(session, group_subject_id)
    if not gs:
        return False, "Дисциплина не найдена."
    gs.subject.kind = kind.value
    await session.commit()
    return True, "Тип дисциплины обновлен."


async def deactivate_group_subject(session: AsyncSession, group_subject_id: int) -> bool:
    gs = await get_group_subject_active(session, group_subject_id)
    if not gs:
        return False
    gs.is_active = False
    await session.commit()
    return True


async def list_group_students_with_user(session: AsyncSession, group_id: int) -> list[Student]:
    stmt = (
        select(Student)
        .options(joinedload(Student.user))
        .where(Student.group_id == group_id)
        .order_by(Student.last_name, Student.first_name, Student.middle_name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_student_with_user(session: AsyncSession, student_id: int) -> Student | None:
    stmt = select(Student).options(joinedload(Student.user)).where(Student.id == student_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_student_to_group(
    session: AsyncSession,
    group_id: int,
    last_name: str,
    first_name: str,
    middle_name: str | None,
) -> Student:
    student = Student(
        group_id=group_id,
        last_name=normalize_name(last_name),
        first_name=normalize_name(first_name),
        middle_name=normalize_name(middle_name) if middle_name else None,
    )
    session.add(student)
    await session.commit()
    await session.refresh(student)
    return student


async def update_student_full_name(
    session: AsyncSession,
    student_id: int,
    last_name: str,
    first_name: str,
    middle_name: str | None,
) -> bool:
    student = await get_student_with_user(session, student_id)
    if not student:
        return False
    student.last_name = normalize_name(last_name)
    student.first_name = normalize_name(first_name)
    student.middle_name = normalize_name(middle_name) if middle_name else None
    await session.commit()
    return True


async def toggle_student_inactive(session: AsyncSession, student_id: int) -> tuple[bool, str]:
    student = await get_student_with_user(session, student_id)
    if not student:
        return False, "Пользователь не найден."
    student.is_inactive = not student.is_inactive
    await session.commit()
    return True, "Статус активности обновлен."


async def set_role_for_student_user(session: AsyncSession, student_id: int, role: Role) -> tuple[bool, str]:
    student = await get_student_with_user(session, student_id)
    if not student:
        return False, "Пользователь не найден."
    if not student.user:
        return False, "У этого студента еще нет Telegram-аккаунта в системе. Пусть выполнит /start."
    student.user.role = role.value
    await session.commit()
    return True, "Роль обновлена."


async def delete_student_with_related(session: AsyncSession, student_id: int) -> bool:
    student = await get_student_with_user(session, student_id)
    if not student:
        return False

    await session.execute(delete(Submission).where(Submission.student_id == student_id))
    if student.user:
        await session.execute(
            update(ScheduleTemplate)
            .where(ScheduleTemplate.uploaded_by_user_id == student.user.id)
            .values(uploaded_by_user_id=None)
        )
        await session.execute(delete(User).where(User.id == student.user.id))
    await session.execute(delete(Student).where(Student.id == student_id))
    await session.commit()
    return True
