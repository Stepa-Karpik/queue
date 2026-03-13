from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import AdminPanelCallback


def admin_main_kb(selected_group: str | None) -> InlineKeyboardMarkup:
    header = f"Текущая группа: {selected_group}" if selected_group else "Группа не выбрана"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=header, callback_data=AdminPanelCallback(action="noop", value="0").pack())],
            [InlineKeyboardButton(text="🏫 Выбрать группу", callback_data=AdminPanelCallback(action="groups", value="1").pack())],
            [InlineKeyboardButton(text="👤 Все зарегистрированные", callback_data=AdminPanelCallback(action="users", value="1").pack())],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data=AdminPanelCallback(action="broadcast", value="0").pack())],
            [InlineKeyboardButton(text="✅ Закрыть", callback_data=AdminPanelCallback(action="close", value="0").pack())],
        ]
    )


def admin_groups_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=AdminPanelCallback(action="select_group", value=str(group_id)).pack())]
        for group_id, label in items
    ]
    rows.extend(_pagination("groups", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_users_kb(items: list[tuple[int, str]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=AdminPanelCallback(action="noop", value=str(user_id)).pack())] for user_id, label in items]
    rows.extend(_pagination("users", page, total_pages))
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminPanelCallback(action="back", value="0").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _pagination(section: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    if total_pages <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️", callback_data=AdminPanelCallback(action=f"{section}_page", value=str(page - 1)).pack()))
    row.append(InlineKeyboardButton(text=f"Страница {page}/{total_pages}", callback_data=AdminPanelCallback(action="noop", value="0").pack()))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="▶️", callback_data=AdminPanelCallback(action=f"{section}_page", value=str(page + 1)).pack()))
    return [row]
