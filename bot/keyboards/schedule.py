from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import ScheduleCallback
from bot.utils.render import keycap_number


def schedule_overview_kb(can_manage: bool, has_schedule: bool) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    if can_manage:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Обновить" if has_schedule else "Загрузить",
                    callback_data=ScheduleCallback(action="upload", value="0").pack(),
                )
            ]
        )
        if has_schedule:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="Привязать к дисциплине",
                        callback_data=ScheduleCallback(action="bind", value="0").pack(),
                    )
                ]
            )
    rows.append([InlineKeyboardButton(text="Назад", callback_data=ScheduleCallback(action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_bind_subjects_kb(items: list[tuple[str, str]], selected_key: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, (discipline_key, _) in enumerate(items, start=1):
        is_selected = discipline_key == selected_key
        row.append(
            InlineKeyboardButton(
                text="🟩" if is_selected else keycap_number(idx),
                callback_data=ScheduleCallback(action="pick_external", value=str(idx)).pack(),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ScheduleCallback(action="back_to_schedule", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def schedule_bind_internal_kb(items: list[tuple[int, str]], selected_subject_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, (subject_id, _) in enumerate(items, start=1):
        is_selected = subject_id == selected_subject_id
        row.append(
            InlineKeyboardButton(
                text="🟩" if is_selected else keycap_number(idx),
                callback_data=ScheduleCallback(action="pick_internal", value=str(idx)).pack(),
            )
        )
        if idx % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=ScheduleCallback(action="bind", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
