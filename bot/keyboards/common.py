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


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Профиль")],
            [KeyboardButton(text="Лабораторные работы")],
            [KeyboardButton(text="Практические занятия")],
        ],
        resize_keyboard=True,
    )


def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True,
    )


def subject_actions_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Назад")],
            [KeyboardButton(text="Очередность сдач")],
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


def sort_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="По алфавиту", callback_data=SortCallback(by="alpha").pack())],
            [InlineKeyboardButton(text="По количеству сданных", callback_data=SortCallback(by="count").pack())],
        ]
    )


def works_kb(numbers: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, num in enumerate(numbers, start=1):
        row.append(InlineKeyboardButton(text=str(num), callback_data=WorkCallback(number=num).pack()))
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Назад", callback_data=ActionCallback(name="work_back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def students_kb(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=StudentCallback(student_id=student_id).pack())]
        for student_id, name in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subject_inline_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сортировка", callback_data=ActionCallback(name="sort").pack())],
            [InlineKeyboardButton(text="Отметить сдачу", callback_data=ActionCallback(name="mark").pack())],
            [InlineKeyboardButton(text="Моя статистика", callback_data=ActionCallback(name="stats").pack())],
        ]
    )


def score_optional_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без балла", callback_data=ActionCallback(name="no_score").pack())],
        ]
    )


def admin_subject_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить дисциплину", callback_data=ActionCallback(name="admin_add_subject").pack())],
            [InlineKeyboardButton(text="Добавить работу", callback_data=ActionCallback(name="admin_add_work").pack())],
            [InlineKeyboardButton(text="Удалить работу", callback_data=ActionCallback(name="admin_remove_work").pack())],
            [InlineKeyboardButton(text="Удалить дисциплину", callback_data=ActionCallback(name="admin_remove_subject").pack())],
        ]
    )


def admin_add_subject_kind_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Лабораторные", callback_data=AddSubjectCallback(kind="lab").pack())],
            [InlineKeyboardButton(text="Практические", callback_data=AddSubjectCallback(kind="practice").pack())],
        ]
    )


def pagination_kb(action: str, page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(
            InlineKeyboardButton(
                text="◀",
                callback_data=PageCallback(action=action, page=page - 1).pack(),
            )
        )
    row.append(InlineKeyboardButton(text=f"Стр. {page}/{total_pages}", callback_data=ActionCallback(name="noop").pack()))
    if page < total_pages:
        row.append(
            InlineKeyboardButton(
                text="▶",
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
    return InlineKeyboardMarkup(inline_keyboard=rows)
