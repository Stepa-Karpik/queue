from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import GroupMenuCallback
from bot.keyboards.common import GROUP_LIST_ALIASES
from bot.keyboards.group import group_menu_kb, group_view_kb
from bot.services.admin_panel import list_group_students_with_user
from bot.services.teachers import list_display_teacher_names
from bot.services.users import get_effective_group, get_user_by_tg
from bot.utils.admin_state import cancel_admin_broadcast_flow
from bot.utils.names import format_short_name, normalize_group_name

router = Router()


def _build_group_menu_text(group_name: str) -> str:
    return f"Группа {group_name}.\nВыберите раздел:"


def _build_group_list_text(group_name: str, students) -> str:
    lines = [f"👥 Список группы {group_name}:", ""]
    for idx, student in enumerate(students, start=1):
        lines.append(f"{idx}. {format_short_name(student.last_name, student.first_name, student.middle_name)}")
    return "\n".join(lines)


def _build_teachers_text(group_name: str, teacher_names: list[str]) -> str:
    if not teacher_names:
        return f"Преподаватели группы {group_name} пока не отмечены."
    lines = [f"Преподаватели группы {group_name}:", ""]
    for idx, teacher_name in enumerate(teacher_names, start=1):
        lines.append(f"{idx}. {teacher_name}")
        if idx != len(teacher_names):
            lines.append("")
    return "\n".join(lines)


@router.message(F.text.in_(GROUP_LIST_ALIASES))
async def group_menu_handler(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        return

    await message.answer(
        _build_group_menu_text(normalize_group_name(group.name)),
        reply_markup=group_menu_kb(),
    )


@router.callback_query(GroupMenuCallback.filter())
async def group_menu_callbacks(call: CallbackQuery, callback_data: GroupMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    await cancel_admin_broadcast_flow(call.message, state)

    user = await get_user_by_tg(session, call.from_user.id)
    if not user:
        await call.message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    group_name = normalize_group_name(group.name)

    if callback_data.action == "menu":
        await call.message.edit_text(_build_group_menu_text(group_name), reply_markup=group_menu_kb())
        return
    if callback_data.action == "list":
        students = await list_group_students_with_user(session, group.id)
        if not students:
            await call.message.edit_text(f"В группе {group_name} пока нет студентов.", reply_markup=group_view_kb())
            return
        await call.message.edit_text(_build_group_list_text(group_name, students), reply_markup=group_view_kb())
        return
    if callback_data.action == "teachers":
        teacher_names = await list_display_teacher_names(session, group.id)
        await call.message.edit_text(_build_teachers_text(group_name, teacher_names), reply_markup=group_view_kb())
        return
    if callback_data.action == "main_menu":
        try:
            await call.message.delete()
        except Exception:  # noqa: BLE001
            pass
