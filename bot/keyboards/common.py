from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.keyboards.callbacks import (
    ConfirmCallback,
    SortCallback,
    WorkCallback,
    StudentCallback,
    SubjectCallback,
    ActionCallback,
    PageCallback,
    AdminWorkCallback,
    AddSubjectCallback,
)
from bot.utils.render import keycap_number

BTN_PROFILE = "👤 Профиль"
BTN_LABS = "🧪 Лабораторные"
BTN_PRACTICE = "📝 Практические"
BTN_HELP = "ℹ️ Как пользоваться"
BTN_BACK_MENU = "⬅️ Главное меню"
BTN_PRIORITY = "📊 Очередность сдач"
BTN_STAROSTA = "🛠 Староста"
BTN_GROUP_LIST = "👥 Список группы"
BTN_SCHEDULE = "📆 Расписание"
BTN_ADMIN = "👑 Админ"
BTN_ADMIN_GROUPS = "🏫 Группы"
BTN_ADMIN_USERS = "👤 Все пользователи"
BTN_ADMIN_BROADCAST = "📣 Рассылка"
BTN_STUDENT_MODE = "Студент"

PROFILE_ALIASES = (BTN_PROFILE, "Профиль")
LABS_ALIASES = (BTN_LABS, "Лабораторные работы")
PRACTICE_ALIASES = (BTN_PRACTICE, "Практические занятия")
HELP_ALIASES = (BTN_HELP, "Помощь")
BACK_ALIASES = (BTN_BACK_MENU, "Назад")
PRIORITY_ALIASES = (BTN_PRIORITY, "Очередность сдач")
STAROSTA_ALIASES = (BTN_STAROSTA, "Староста")
GROUP_LIST_ALIASES = (BTN_GROUP_LIST, "Список группы")
SCHEDULE_ALIASES = (BTN_SCHEDULE, "Расписание")
ADMIN_ALIASES = (BTN_ADMIN, "Админ")
ADMIN_GROUPS_ALIASES = (BTN_ADMIN_GROUPS, "Группы")
ADMIN_USERS_ALIASES = (BTN_ADMIN_USERS, "Все пользователи")
ADMIN_BROADCAST_ALIASES = (BTN_ADMIN_BROADCAST, "Рассылка")
STUDENT_MODE_ALIASES = (BTN_STUDENT_MODE, "Режим студента")


def admin_mode_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADMIN_GROUPS), KeyboardButton(text=BTN_ADMIN_USERS)],
            [KeyboardButton(text=BTN_SCHEDULE), KeyboardButton(text=BTN_GROUP_LIST)],
            [KeyboardButton(text=BTN_STAROSTA), KeyboardButton(text=BTN_ADMIN_BROADCAST)],
            [KeyboardButton(text=BTN_STUDENT_MODE)],
        ],
        resize_keyboard=True,
    )


def main_menu_kb(is_starosta: bool = False, is_admin: bool = False, admin_mode: bool = False) -> ReplyKeyboardMarkup:
    if admin_mode:
        return admin_mode_menu_kb()
    keyboard = [
        [KeyboardButton(text=BTN_LABS), KeyboardButton(text=BTN_PRACTICE)],
        [KeyboardButton(text=BTN_SCHEDULE), KeyboardButton(text=BTN_GROUP_LIST)],
        [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_HELP)],
    ]
    if is_starosta or is_admin:
        keyboard.append([KeyboardButton(text=BTN_STAROSTA)])
    if is_admin:
        keyboard.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BACK_MENU)]],
        resize_keyboard=True,
    )


def subject_actions_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PRIORITY)],
            [KeyboardButton(text=BTN_BACK_MENU)],
        ],
        resize_keyboard=True,
    )


def confirm_kb(action: str, value: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да",
                    callback_data=ConfirmCallback(action=action, value=value).pack(),
                ),
                InlineKeyboardButton(
                    text="Нет",
                    callback_data=ConfirmCallback(action=action, value="no").pack(),
                ),
            ]
        ]
    )


def subjects_kb(items: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=SubjectCallback(group_subject_id=gs_id, kind=kind).pack())]
        for gs_id, name, kind in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Выйти", callback_data=ActionCallback(name="logout").pack())]
        ]
    )


def sort_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="По фамилии (А-Я)", callback_data=SortCallback(by="alpha").pack())],
            [InlineKeyboardButton(text="По прогрессу (сначала активные)", callback_data=SortCallback(by="count").pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ActionCallback(name="subject_back").pack())],
        ]
    )


def works_kb(numbers: list[int], submitted_numbers: list[int] | set[int] | None = None) -> InlineKeyboardMarkup:
    submitted_set = set(submitted_numbers or [])
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, num in enumerate(numbers, start=1):
        is_submitted = num in submitted_set
        row.append(
            InlineKeyboardButton(
                text="🟩" if is_submitted else keycap_number(num),
                callback_data=ActionCallback(name="noop").pack() if is_submitted else WorkCallback(number=num).pack(),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплине", callback_data=ActionCallback(name="work_back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def students_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=StudentCallback(student_id=student_id).pack())]
        for student_id, name in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subject_view_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav = pagination_kb("subject", page, total_pages)
    if nav:
        rows.extend(nav.inline_keyboard)
    rows.extend(
        [
            [InlineKeyboardButton(text="↕️ Изменить сортировку", callback_data=ActionCallback(name="sort").pack())],
            [InlineKeyboardButton(text="✅ Отметить сдачу", callback_data=ActionCallback(name="mark").pack())],
            [InlineKeyboardButton(text="📈 Моя статистика", callback_data=ActionCallback(name="stats").pack())],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subject_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=ActionCallback(name="subject_back").pack())]
        ]
    )


def score_optional_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без балла", callback_data=ActionCallback(name="no_score").pack())],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data=ActionCallback(name="cancel_score").pack())],
        ]
    )


def admin_add_subject_kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧪 Лабораторные", callback_data=AddSubjectCallback(kind="lab").pack())],
            [InlineKeyboardButton(text="📝 Практические", callback_data=AddSubjectCallback(kind="practice").pack())],
        ]
    )


def pagination_kb(action: str, page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=PageCallback(action=action, page=page - 1).pack(),
            )
        )
    row.append(
        InlineKeyboardButton(text=f"Страница {page}/{total_pages}", callback_data=ActionCallback(name="noop").pack())
    )
    if page < total_pages:
        row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=PageCallback(action=action, page=page + 1).pack(),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[row])


def students_paginated_kb(
    items: list[tuple[int, str]],
    action: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=StudentCallback(student_id=student_id).pack())]
        for student_id, name in items
    ]
    nav = pagination_kb(action, page, total_pages)
    if nav:
        rows.extend(nav.inline_keyboard)
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплине", callback_data=ActionCallback(name="mark_back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_remove_works_kb(numbers: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, num in enumerate(numbers, start=1):
        row.append(
            InlineKeyboardButton(
                text=str(num),
                callback_data=AdminWorkCallback(action="remove_work", number=num).pack(),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ К дисциплине", callback_data=ActionCallback(name="work_back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
