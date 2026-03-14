from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import ActionCallback
from bot.keyboards.common import PROFILE_ALIASES, profile_kb
from bot.models import Role
from bot.services.students import get_student_group
from bot.services.users import delete_user_by_tg, get_user_by_tg, is_admin_mode, is_admin_user
from bot.states.registration import RegistrationStates
from bot.utils.names import format_full_name, normalize_group_name

router = Router()


@router.message(F.text.in_(PROFILE_ALIASES))
async def profile_handler(message: Message, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    role = "Староста" if user.role == Role.STAROSTA.value else "Студент"
    own_group = await get_student_group(session, user.student_id) if user.student_id else None
    faculty = own_group.faculty.name if own_group and own_group.faculty else "—"
    group_name = normalize_group_name(own_group.name) if own_group else "—"

    if user.student:
        full_name = format_full_name(user.student.last_name, user.student.first_name, user.student.middle_name)
    else:
        full_name = message.from_user.full_name

    lines = [
        "Ваш профиль:",
        f"• ФИО: {full_name}",
        f"• Группа: {group_name}",
        f"• Факультет: {faculty}",
        f"• Роль: {role}",
    ]
    if is_admin_user(user):
        selected_group = normalize_group_name(user.admin_group.name) if user.admin_group else "—"
        lines.append("• Права: админ")
        lines.append(f"• Режим: {'админ' if is_admin_mode(user) else 'студент'}")
        lines.append(f"• Выбранная группа админа: {selected_group}")

    await message.answer("\n".join(lines), reply_markup=profile_kb())


@router.callback_query(ActionCallback.filter(F.name == "logout"))
async def logout_handler(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer("Вы вышли из аккаунта.")
    await delete_user_by_tg(session, call.from_user.id)
    await state.clear()
    await call.message.answer(
        "Вы вышли из аккаунта.\n"
        "Начинаем регистрацию заново.\n"
        "Шаг 1 из 3: введите вашу фамилию.\n"
        "Регистр не важен.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(RegistrationStates.waiting_last_name)
