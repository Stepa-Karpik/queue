from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import PROFILE_ALIASES, main_menu_kb
from bot.models import Role
from bot.services.users import get_user_by_tg
from bot.services.students import get_student_group
from bot.utils.names import format_full_name

router = Router()


@router.message(F.text.in_(PROFILE_ALIASES))
async def profile_handler(message: Message, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    student = user.student
    group = await get_student_group(session, student.id)
    role = "Староста" if user.role == Role.STAROSTA.value else "Студент"
    faculty = group.faculty.name if group and group.faculty else "—"
    group_name = group.name if group else "—"
    full_name = format_full_name(student.last_name, student.first_name, student.middle_name)

    text = (
        "Ваш профиль:\n"
        f"• ФИО: {full_name}\n"
        f"• Группа: {group_name}\n"
        f"• Факультет: {faculty}\n"
        f"• Роль: {role}"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_starosta=user.role == Role.STAROSTA.value))
