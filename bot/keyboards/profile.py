from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import ProfileCallback
from bot.utils.user_settings import NotificationMode, get_notification_mode_label


def profile_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Настройки", callback_data=ProfileCallback(section="profile", action="settings", value="0").pack())],
            [InlineKeyboardButton(text="Выйти", callback_data=ProfileCallback(section="profile", action="logout", value="0").pack())],
        ]
    )


def profile_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Уведомления", callback_data=ProfileCallback(section="settings", action="notifications", value="0").pack())],
            [InlineKeyboardButton(text="ФИО", callback_data=ProfileCallback(section="settings", action="full_name", value="0").pack())],
            [InlineKeyboardButton(text="Факультет", callback_data=ProfileCallback(section="settings", action="faculty", value="0").pack())],
            [InlineKeyboardButton(text="Группа", callback_data=ProfileCallback(section="settings", action="group", value="0").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=ProfileCallback(section="settings", action="back", value="0").pack())],
        ]
    )


def notification_modes_kb(current_mode: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for mode in (
        NotificationMode.ENABLED.value,
        NotificationMode.DISABLED.value,
        NotificationMode.AUTO.value,
        NotificationMode.MANUAL.value,
    ):
        label = get_notification_mode_label(mode)
        if mode == current_mode:
            label = f"{label} 🟩"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=ProfileCallback(section="notifications", action="set_mode", value=mode).pack(),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="Назад", callback_data=ProfileCallback(section="notifications", action="back", value="0").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manual_notification_subjects_kb(items: list[tuple[int, str]], selected_ids: set[int]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{name} {'🟩' if group_subject_id in selected_ids else ''}".strip(),
                callback_data=ProfileCallback(section="manual_subjects", action="toggle", value=str(group_subject_id)).pack(),
            )
        ]
        for group_subject_id, name in items
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=ProfileCallback(section="manual_subjects", action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_cancel_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отменить", callback_data=ProfileCallback(section="edit", action="cancel", value="0").pack())]
        ]
    )
