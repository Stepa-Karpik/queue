from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import (
    ManageMenuCallback,
    ManagePageCallback,
    ManageRemoveWorkCallback,
    ManageRoleCallback,
    ManageSubmissionActionCallback,
    ManageSubmissionSubjectCallback,
    ManageSubmissionWorkCallback,
    ManageStudentCallback,
    ManageSubjectCallback,
    ManageTeacherCallback,
    ManageTeacherDisciplineCallback,
    ManageTeacherLessonTypeCallback,
)
from bot.models import Role
from bot.utils.submission_flow import get_submission_work_action
from bot.utils.teacher_names import teacher_lesson_type_label
from bot.utils.render import keycap_number


def management_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Пользователи", callback_data=ManageMenuCallback(section="main", action="users").pack())],
            [InlineKeyboardButton(text="📚 Дисциплины", callback_data=ManageMenuCallback(section="main", action="subjects").pack())],
            [InlineKeyboardButton(text="👨‍🏫 Преподаватели", callback_data=ManageMenuCallback(section="main", action="teachers").pack())],
            [InlineKeyboardButton(text="✅ Выйти из режима", callback_data=ManageMenuCallback(section="main", action="exit").pack())],
        ]
    )


def management_users_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data=ManageMenuCallback(section="users", action="add").pack())],
            [InlineKeyboardButton(text="🧾 Открыть список", callback_data=ManageMenuCallback(section="users", action="list").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="users", action="back").pack())],
        ]
    )


def management_subjects_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить дисциплину", callback_data=ManageMenuCallback(section="subjects", action="add").pack())],
            [InlineKeyboardButton(text="🧾 Открыть список", callback_data=ManageMenuCallback(section="subjects", action="list").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="subjects", action="back").pack())],
        ]
    )


def management_teachers_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data=ManageMenuCallback(section="teachers", action="add").pack())],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data=ManageMenuCallback(section="teachers", action="edit").pack())],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=ManageMenuCallback(section="teachers", action="delete").pack())],
            [InlineKeyboardButton(text="🔄 Спарсить", callback_data=ManageMenuCallback(section="teachers", action="parse").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="teachers", action="back").pack())],
        ]
    )


def management_students_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=ManageStudentCallback(action="view", student_id=student_id).pack())]
        for student_id, name in items
    ]
    rows.extend(_pagination("users", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="users", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_teachers_kb(items: list[tuple[int, str]], action: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=ManageTeacherCallback(action=action, teacher_id=teacher_id).pack())]
        for teacher_id, name in items
    ]
    rows.append([InlineKeyboardButton(text="⬅️ К видам пары", callback_data=ManageMenuCallback(section="teacher_types", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_teacher_disciplines_kb(items: list[str], action: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=ManageTeacherDisciplineCallback(action=action, option_index=index).pack(),
            )
        ]
        for index, name in enumerate(items)
    ]
    rows.append([InlineKeyboardButton(text="⬅️ К преподавателям", callback_data=ManageMenuCallback(section="teachers", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_teacher_lesson_types_kb(items: list[str], action: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=teacher_lesson_type_label(lesson_type),
                callback_data=ManageTeacherLessonTypeCallback(action=action, option_index=index).pack(),
            )
        ]
        for index, lesson_type in enumerate(items)
    ]
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплинам", callback_data=ManageMenuCallback(section="teachers", action=action).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_subjects_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=ManageSubjectCallback(action="view", group_subject_id=group_subject_id).pack())]
        for group_subject_id, name in items
    ]
    rows.extend(_pagination("subjects", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="subjects", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_user_card_kb(student_id: int, is_inactive: bool) -> InlineKeyboardMarkup:
    toggle_label = "Сделать активным" if is_inactive else "Неактивен"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=ManageStudentCallback(action="rename", student_id=student_id).pack())],
            [InlineKeyboardButton(text="🛡 Изменить роль", callback_data=ManageStudentCallback(action="role", student_id=student_id).pack())],
            [InlineKeyboardButton(text="📋 Сдачи", callback_data=ManageStudentCallback(action="submissions", student_id=student_id).pack())],
            [InlineKeyboardButton(text=toggle_label, callback_data=ManageStudentCallback(action="inactive", student_id=student_id).pack())],
            [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data=ManageStudentCallback(action="delete", student_id=student_id).pack())],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=ManageMenuCallback(section="user_card", action="back").pack())],
        ]
    )


def management_submission_actions_kb(student_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отметить сдачу", callback_data=ManageSubmissionActionCallback(mode="add", student_id=student_id).pack())],
            [InlineKeyboardButton(text="❌ Отменить сдачу", callback_data=ManageSubmissionActionCallback(mode="delete", student_id=student_id).pack())],
            [InlineKeyboardButton(text="⬅️ К пользователю", callback_data=ManageStudentCallback(action="view", student_id=student_id).pack())],
        ]
    )


def management_role_kb(student_id: int, current_role: str | None) -> InlineKeyboardMarkup:
    student_label = "✅ Студент" if current_role == Role.STUDENT.value else "Студент"
    starosta_label = "✅ Староста" if current_role == Role.STAROSTA.value else "Староста"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=student_label, callback_data=ManageRoleCallback(student_id=student_id, role=Role.STUDENT.value).pack()),
                InlineKeyboardButton(text=starosta_label, callback_data=ManageRoleCallback(student_id=student_id, role=Role.STAROSTA.value).pack()),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageStudentCallback(action="view", student_id=student_id).pack())],
        ]
    )


def management_subject_card_kb(group_subject_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=ManageSubjectCallback(action="rename", group_subject_id=group_subject_id).pack())],
            [InlineKeyboardButton(text="🔁 Сменить тип", callback_data=ManageSubjectCallback(action="kind", group_subject_id=group_subject_id).pack())],
            [InlineKeyboardButton(text="➕ Добавить работу", callback_data=ManageSubjectCallback(action="add_work", group_subject_id=group_subject_id).pack())],
            [InlineKeyboardButton(text="➖ Удалить работу", callback_data=ManageSubjectCallback(action="remove_work", group_subject_id=group_subject_id).pack())],
            [InlineKeyboardButton(text="🗑 Удалить дисциплину", callback_data=ManageSubjectCallback(action="delete", group_subject_id=group_subject_id).pack())],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=ManageMenuCallback(section="subject_card", action="back").pack())],
        ]
    )


def management_subject_kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧪 Лабораторные", callback_data=ManageMenuCallback(section="subject_kind", action="lab").pack())],
            [InlineKeyboardButton(text="📝 Практические", callback_data=ManageMenuCallback(section="subject_kind", action="practice").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageMenuCallback(section="subject_kind", action="back").pack())],
        ]
    )


def management_remove_works_kb(numbers: list[int], group_subject_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, number in enumerate(numbers, start=1):
        row.append(
            InlineKeyboardButton(
                text=keycap_number(number),
                callback_data=ManageRemoveWorkCallback(group_subject_id=group_subject_id, work_number=number).pack(),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ManageSubjectCallback(action="view", group_subject_id=group_subject_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_submission_subjects_kb(items: list[tuple[int, str]], student_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=ManageSubmissionSubjectCallback(mode="select", student_id=student_id, group_subject_id=group_subject_id).pack())]
        for group_subject_id, name in items
    ]
    rows.append([InlineKeyboardButton(text="⬅️ К действиям", callback_data=ManageStudentCallback(action="submissions", student_id=student_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_submission_works_kb(
    group_subject_id: int,
    student_id: int,
    numbers: list[int],
    submitted_numbers: list[int] | set[int],
    mode: str,
) -> InlineKeyboardMarkup:
    submitted_set = set(submitted_numbers)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, number in enumerate(numbers, start=1):
        is_submitted = number in submitted_set
        action = get_submission_work_action(mode, is_submitted=is_submitted)
        row.append(
            InlineKeyboardButton(
                text=("🟥" if mode == "delete" else "🟩") if is_submitted else keycap_number(number),
                callback_data=(
                    ManageSubmissionWorkCallback(
                        mode=action,
                        student_id=student_id,
                        group_subject_id=group_subject_id,
                        work_number=number,
                    ).pack()
                    if action != "noop"
                    else ManageMenuCallback(section="noop", action="noop").pack()
                ),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплинам", callback_data=ManageStudentCallback(action="submission_subjects", student_id=student_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def management_score_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без балла", callback_data=ManageMenuCallback(section="submission_score", action="none").pack())],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=ManageMenuCallback(section="submission_score", action="cancel").pack())],
        ]
    )


def _pagination(section: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    if total_pages <= 1:
        return []

    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️", callback_data=ManagePageCallback(section=section, page=page - 1).pack()))
    row.append(InlineKeyboardButton(text=f"Страница {page}/{total_pages}", callback_data=ManageMenuCallback(section="noop", action="noop").pack()))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="▶️", callback_data=ManagePageCallback(section=section, page=page + 1).pack()))
    return [row]
