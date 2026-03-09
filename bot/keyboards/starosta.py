from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import (
    ConfirmCallback,
    StarostaMenuCallback,
    StarostaPageCallback,
    StarostaRoleCallback,
    StarostaStudentCallback,
    StarostaSubjectCallback,
    StarostaWorkCallback,
)
from bot.models import Role


def starosta_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Дисциплины", callback_data=StarostaMenuCallback(section="main", action="subjects").pack())],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data=StarostaMenuCallback(section="main", action="users").pack())],
            [InlineKeyboardButton(text="✅ Выйти из режима", callback_data=StarostaMenuCallback(section="main", action="exit").pack())],
        ]
    )


def starosta_subjects_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить дисциплину", callback_data=StarostaMenuCallback(section="subjects", action="add").pack())],
            [InlineKeyboardButton(text="✏️ Редактировать дисциплину", callback_data=StarostaMenuCallback(section="subjects", action="edit").pack())],
            [InlineKeyboardButton(text="🗑 Удалить дисциплину", callback_data=StarostaMenuCallback(section="subjects", action="delete").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="subjects", action="back").pack())],
        ]
    )


def starosta_users_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data=StarostaMenuCallback(section="users", action="add").pack())],
            [InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data=StarostaMenuCallback(section="users", action="edit").pack())],
            [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data=StarostaMenuCallback(section="users", action="delete").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="users", action="back").pack())],
        ]
    )


def starosta_subject_kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧪 Лабораторные", callback_data=StarostaMenuCallback(section="subject_kind", action="lab").pack())],
            [InlineKeyboardButton(text="📝 Практические", callback_data=StarostaMenuCallback(section="subject_kind", action="practice").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="subject_kind", action="back").pack())],
        ]
    )


def starosta_subject_edit_kb(group_subject_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=StarostaMenuCallback(section="subject_edit", action=f"rename|{group_subject_id}").pack())],
            [InlineKeyboardButton(text="🔁 Сменить тип", callback_data=StarostaMenuCallback(section="subject_edit", action=f"kind|{group_subject_id}").pack())],
            [InlineKeyboardButton(text="➕ Добавить работу", callback_data=StarostaMenuCallback(section="subject_edit", action=f"add_work|{group_subject_id}").pack())],
            [InlineKeyboardButton(text="➖ Удалить работу", callback_data=StarostaMenuCallback(section="subject_edit", action=f"remove_work|{group_subject_id}").pack())],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=StarostaMenuCallback(section="subject_edit", action="back").pack())],
        ]
    )


def starosta_user_edit_kb(student_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=StarostaMenuCallback(section="user_edit", action=f"rename|{student_id}").pack())],
            [InlineKeyboardButton(text="🛡 Изменить роль", callback_data=StarostaMenuCallback(section="user_edit", action=f"role|{student_id}").pack())],
            [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data=StarostaMenuCallback(section="user_edit", action=f"delete|{student_id}").pack())],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=StarostaMenuCallback(section="user_edit", action="back").pack())],
        ]
    )


def starosta_role_kb(student_id: int, current_role: str | None) -> InlineKeyboardMarkup:
    student_label = "✅ Студент" if current_role == Role.STUDENT.value else "Студент"
    starosta_label = "✅ Староста" if current_role == Role.STAROSTA.value else "Староста"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=student_label, callback_data=StarostaRoleCallback(student_id=student_id, role=Role.STUDENT.value).pack()),
                InlineKeyboardButton(text=starosta_label, callback_data=StarostaRoleCallback(student_id=student_id, role=Role.STAROSTA.value).pack()),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="user_edit", action=f"back_to_user|{student_id}").pack())],
        ]
    )


def starosta_subjects_list_kb(
    items: list[tuple[int, str]],
    mode: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=StarostaSubjectCallback(mode=mode, group_subject_id=group_subject_id).pack(),
            )
        ]
        for group_subject_id, name in items
    ]
    _append_pagination(rows, section="subjects", mode=mode, page=page, total_pages=total_pages)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="subjects", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def starosta_students_list_kb(
    items: list[tuple[int, str]],
    mode: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=StarostaStudentCallback(mode=mode, student_id=student_id).pack(),
            )
        ]
        for student_id, name in items
    ]
    _append_pagination(rows, section="users", mode=mode, page=page, total_pages=total_pages)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=StarostaMenuCallback(section="users", action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def starosta_remove_work_kb(numbers: list[int], group_subject_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, num in enumerate(numbers, start=1):
        row.append(InlineKeyboardButton(text=str(num), callback_data=StarostaWorkCallback(action=f"remove|{group_subject_id}", number=num).pack()))
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплине", callback_data=StarostaMenuCallback(section="subject_edit", action=f"back_to_subject|{group_subject_id}").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def starosta_delete_subject_confirm_kb(group_subject_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=ConfirmCallback(action="st_delete_subject", value=str(group_subject_id)).pack(),
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=StarostaMenuCallback(section="subjects", action="back").pack(),
                ),
            ]
        ]
    )


def starosta_delete_user_confirm_kb(student_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=ConfirmCallback(action="st_delete_user", value=str(student_id)).pack(),
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=StarostaMenuCallback(section="users", action="back").pack(),
                ),
            ]
        ]
    )


def _append_pagination(
    rows: list[list[InlineKeyboardButton]],
    section: str,
    mode: str,
    page: int,
    total_pages: int,
) -> None:
    if total_pages <= 1:
        return
    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=StarostaPageCallback(section=section, mode=mode, page=page - 1).pack(),
            )
        )
    nav_row.append(InlineKeyboardButton(text=f"Страница {page}/{total_pages}", callback_data=StarostaMenuCallback(section="noop", action="noop").pack()))
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=StarostaPageCallback(section=section, mode=mode, page=page + 1).pack(),
            )
        )
    rows.append(nav_row)
