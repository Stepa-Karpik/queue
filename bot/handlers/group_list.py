from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import GROUP_LIST_ALIASES
from bot.services.admin_panel import list_group_students_with_user
from bot.services.users import get_effective_group, get_user_by_tg
from bot.utils.names import format_short_name, normalize_group_name

router = Router()


@router.message(F.text.in_(GROUP_LIST_ALIASES))
async def group_list_handler(message: Message, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        return

    students = await list_group_students_with_user(session, group.id)
    if not students:
        await message.answer("В группе пока нет студентов.")
        return

    lines = [f"👥 Список группы {normalize_group_name(group.name)}:", ""]
    for idx, student in enumerate(students, start=1):
        lines.append(f"{idx}. {format_short_name(student.last_name, student.first_name, student.middle_name)}")
    await message.answer("\n".join(lines))
