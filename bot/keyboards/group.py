from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import GroupMenuCallback


def group_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Список группы", callback_data=GroupMenuCallback(action="list", value="0").pack())],
            [InlineKeyboardButton(text="Преподаватели", callback_data=GroupMenuCallback(action="teachers", value="0").pack())],
            [InlineKeyboardButton(text="Главное меню", callback_data=GroupMenuCallback(action="main_menu", value="0").pack())],
        ]
    )


def group_view_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=GroupMenuCallback(action="menu", value="0").pack())],
            [InlineKeyboardButton(text="Главное меню", callback_data=GroupMenuCallback(action="main_menu", value="0").pack())],
        ]
    )
