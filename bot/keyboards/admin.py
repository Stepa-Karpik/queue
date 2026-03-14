from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import AdminPanelCallback
from bot.models import Role


def admin_groups_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=AdminPanelCallback(action="select_group", value=str(group_id)).pack())]
        for group_id, label in items
    ]
    rows.extend(_pagination("groups_page", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_users_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=AdminPanelCallback(action="user_view", value=str(user_id)).pack())]
        for user_id, label in items
    ]
    rows.extend(_pagination("users_page", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_card_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data=AdminPanelCallback(action="user_rename", value=str(user_id)).pack())],
            [InlineKeyboardButton(text="🛡 Изменить роль", callback_data=AdminPanelCallback(action="user_role", value=str(user_id)).pack())],
            [InlineKeyboardButton(text="🏫 Сменить группу", callback_data=AdminPanelCallback(action="user_group", value=str(user_id)).pack())],
            [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data=AdminPanelCallback(action="user_delete", value=str(user_id)).pack())],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=AdminPanelCallback(action="user_back", value="0").pack())],
        ]
    )


def admin_user_role_kb(user_id: int, current_role: str) -> InlineKeyboardMarkup:
    student_label = "✅ Студент" if current_role == Role.STUDENT.value else "Студент"
    starosta_label = "✅ Староста" if current_role == Role.STAROSTA.value else "Староста"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=student_label,
                    callback_data=AdminPanelCallback(action="user_set_role", value=f"{user_id}:{Role.STUDENT.value}").pack(),
                ),
                InlineKeyboardButton(
                    text=starosta_label,
                    callback_data=AdminPanelCallback(action="user_set_role", value=f"{user_id}:{Role.STAROSTA.value}").pack(),
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="user_view", value=str(user_id)).pack())],
        ]
    )


def admin_user_groups_kb(items: list[tuple[int, str]], user_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=AdminPanelCallback(action="user_pick_group", value=f"{user_id}:{group_id}").pack(),
            )
        ]
        for group_id, label in items
    ]
    rows.extend(_pagination("user_groups_page", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="user_view", value=str(user_id)).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pagination(action: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    if total_pages <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️", callback_data=AdminPanelCallback(action=action, value=str(page - 1)).pack()))
    row.append(InlineKeyboardButton(text=f"Страница {page}/{total_pages}", callback_data=AdminPanelCallback(action="noop", value="0").pack()))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="▶️", callback_data=AdminPanelCallback(action=action, value=str(page + 1)).pack()))
    return [row]
