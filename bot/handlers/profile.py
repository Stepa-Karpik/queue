from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import ProfileCallback
from bot.keyboards.common import PROFILE_ALIASES, main_menu_kb
from bot.keyboards.profile import (
    manual_notification_subjects_kb,
    notification_modes_kb,
    profile_cancel_edit_kb,
    profile_main_kb,
    profile_settings_kb,
)
from bot.models import Role
from bot.services.admin_panel import list_group_subjects_all, reassign_student_group, update_student_full_name
from bot.services.preferences import (
    all_notification_modes,
    clear_user_manual_notification_subjects_for_group_change,
    list_user_manual_notification_subject_ids,
    set_user_notification_mode,
    toggle_user_manual_notification_subject,
)
from bot.services.roster import get_or_create_faculty, get_or_create_group
from bot.services.students import get_student_group
from bot.services.users import delete_user_by_tg, get_user_by_tg, is_admin_mode, is_admin_user
from bot.states.profile_settings import ProfileSettingsStates
from bot.states.registration import RegistrationStates
from bot.utils.names import (
    format_full_name,
    get_group_validation_error_text,
    normalize_faculty_name,
    normalize_group_name,
    normalize_name,
    normalize_valid_group_name,
    split_full_name,
)
from bot.utils.user_settings import (
    NotificationMode,
    get_notification_mode_description,
    get_notification_mode_label,
)

router = Router()


def _build_profile_text(user, fallback_full_name: str) -> str:
    role = "Староста" if user.role == Role.STAROSTA.value else "Студент"
    own_group = user.student.group if user.student else None
    faculty = normalize_faculty_name(own_group.faculty.name) if own_group and own_group.faculty else "—"
    group_name = normalize_group_name(own_group.name) if own_group else "—"
    full_name = (
        format_full_name(user.student.last_name, user.student.first_name, user.student.middle_name)
        if user.student
        else fallback_full_name
    )

    lines = [
        "Ваш профиль:",
        f"• ФИО: {full_name}",
        f"• Группа: {group_name}",
        f"• Факультет: {faculty}",
        f"• Роль: {role}",
        f"• Уведомления: {get_notification_mode_label(user.notification_mode)}",
    ]
    if is_admin_user(user):
        selected_group = normalize_group_name(user.admin_group.name) if user.admin_group else "—"
        lines.append("• Права: админ")
        lines.append(f"• Режим: {'админ' if is_admin_mode(user) else 'студент'}")
        lines.append(f"• Выбранная группа админа: {selected_group}")
    return "\n".join(lines)


def _build_settings_text(user) -> str:
    own_group = user.student.group if user.student else None
    faculty = normalize_faculty_name(own_group.faculty.name) if own_group and own_group.faculty else "—"
    group_name = normalize_group_name(own_group.name) if own_group else "—"
    full_name = (
        format_full_name(user.student.last_name, user.student.first_name, user.student.middle_name)
        if user.student
        else "—"
    )
    lines = [
        "Настройки профиля:",
        f"ФИО: {full_name}",
        f"Факультет: {faculty}",
        f"Группа: {group_name}",
        f"Уведомления: {get_notification_mode_label(user.notification_mode)}",
        "",
        "Выберите, что хотите изменить.",
    ]
    return "\n".join(lines)


def _build_notification_settings_text(current_mode: str) -> str:
    lines = [
        "Настройки уведомлений:",
        "",
        get_notification_mode_description(NotificationMode.ENABLED.value),
        get_notification_mode_description(NotificationMode.DISABLED.value),
        get_notification_mode_description(NotificationMode.AUTO.value),
        get_notification_mode_description(NotificationMode.MANUAL.value),
        "",
        f"Сейчас выбрано: {get_notification_mode_label(current_mode)}",
    ]
    return "\n".join(lines)


async def _render_screen(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup,
    *,
    edit_message_id: int | None = None,
) -> None:
    target_message_id = edit_message_id
    if target_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=target_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            await state.update_data(profile_screen_message_id=target_message_id)
            return
        except Exception as exc:  # noqa: BLE001
            if "message is not modified" in str(exc).lower():
                await state.update_data(profile_screen_message_id=target_message_id)
                return

    sent = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(profile_screen_message_id=sent.message_id)


async def _show_profile_screen(message: Message, state: FSMContext, session: AsyncSession, tg_id: int, fallback_full_name: str):
    user = await get_user_by_tg(session, tg_id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    data = await state.get_data()
    await _render_screen(
        message,
        state,
        _build_profile_text(user, fallback_full_name),
        profile_main_kb(),
        edit_message_id=data.get("profile_screen_message_id"),
    )


async def _show_settings_screen(message: Message, state: FSMContext, session: AsyncSession, tg_id: int):
    user = await get_user_by_tg(session, tg_id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    data = await state.get_data()
    await _render_screen(
        message,
        state,
        _build_settings_text(user),
        profile_settings_kb(),
        edit_message_id=data.get("profile_screen_message_id"),
    )


async def _show_notification_modes_screen(message: Message, state: FSMContext, session: AsyncSession, tg_id: int):
    user = await get_user_by_tg(session, tg_id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    data = await state.get_data()
    await _render_screen(
        message,
        state,
        _build_notification_settings_text(user.notification_mode),
        notification_modes_kb(user.notification_mode),
        edit_message_id=data.get("profile_screen_message_id"),
    )


async def _show_manual_subjects_screen(message: Message, state: FSMContext, session: AsyncSession, tg_id: int):
    user = await get_user_by_tg(session, tg_id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_student_group(session, user.student_id)
    if not group:
        await message.answer("Сначала укажите группу.")
        return

    subjects = await list_group_subjects_all(session, group.id)
    selected_ids = await list_user_manual_notification_subject_ids(session, user.id)
    items = [(item.id, item.subject.name) for item in subjects]
    text = (
        "Выберите дисциплины для ручных уведомлений.\n"
        "Зеленый квадрат показывает, что уведомления по предмету включены."
    )
    data = await state.get_data()
    await _render_screen(
        message,
        state,
        text,
        manual_notification_subjects_kb(items, selected_ids),
        edit_message_id=data.get("profile_screen_message_id"),
    )


@router.message(F.text.in_(PROFILE_ALIASES))
async def profile_handler(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    await state.update_data(profile_pending_faculty=None)
    await state.set_state(None)
    await _show_profile_screen(message, state, session, message.from_user.id, message.from_user.full_name)


@router.callback_query(ProfileCallback.filter())
async def profile_callbacks(call: CallbackQuery, callback_data: ProfileCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user:
        await call.message.answer("Сначала зарегистрируйтесь через /start.")
        return

    await state.update_data(profile_screen_message_id=call.message.message_id)

    if callback_data.section == "profile":
        if callback_data.action == "settings":
            await _show_settings_screen(call.message, state, session, call.from_user.id)
            return
        if callback_data.action == "logout":
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
            return

    if callback_data.section == "settings":
        if callback_data.action == "back":
            await _show_profile_screen(call.message, state, session, call.from_user.id, call.from_user.full_name)
            return
        if callback_data.action == "notifications":
            await _show_notification_modes_screen(call.message, state, session, call.from_user.id)
            return
        if callback_data.action == "full_name":
            await state.set_state(ProfileSettingsStates.waiting_full_name)
            await _render_screen(
                call.message,
                state,
                "Введите новое ФИО.",
                profile_cancel_edit_kb(),
                edit_message_id=call.message.message_id,
            )
            return
        if callback_data.action == "faculty":
            await state.set_state(ProfileSettingsStates.waiting_faculty)
            await _render_screen(
                call.message,
                state,
                "Введите новый факультет.\nПосле этого нужно будет указать новую группу.",
                profile_cancel_edit_kb(),
                edit_message_id=call.message.message_id,
            )
            return
        if callback_data.action == "group":
            await state.set_state(ProfileSettingsStates.waiting_group)
            await _render_screen(
                call.message,
                state,
                "Введите новую группу.",
                profile_cancel_edit_kb(),
                edit_message_id=call.message.message_id,
            )
            return

    if callback_data.section == "notifications":
        if callback_data.action == "back":
            await _show_settings_screen(call.message, state, session, call.from_user.id)
            return
        if callback_data.action == "set_mode":
            if callback_data.value not in all_notification_modes():
                await call.message.answer("Не удалось обновить настройку уведомлений.")
                return
            await set_user_notification_mode(session, user, callback_data.value)
            if callback_data.value == NotificationMode.MANUAL.value:
                await _show_manual_subjects_screen(call.message, state, session, call.from_user.id)
                return
            await _show_notification_modes_screen(call.message, state, session, call.from_user.id)
            return
        if callback_data.action == "manual_subjects":
            if user.notification_mode != NotificationMode.MANUAL.value:
                await set_user_notification_mode(session, user, NotificationMode.MANUAL.value)
            await _show_manual_subjects_screen(call.message, state, session, call.from_user.id)
            return

    if callback_data.section == "manual_subjects":
        if callback_data.action == "back":
            await _show_notification_modes_screen(call.message, state, session, call.from_user.id)
            return
        if callback_data.action == "toggle":
            if user.notification_mode != NotificationMode.MANUAL.value:
                await set_user_notification_mode(session, user, NotificationMode.MANUAL.value)
            await toggle_user_manual_notification_subject(session, user.id, int(callback_data.value))
            await _show_manual_subjects_screen(call.message, state, session, call.from_user.id)
            return

    if callback_data.section == "edit" and callback_data.action == "cancel":
        await state.update_data(profile_pending_faculty=None)
        await state.set_state(None)
        await _show_settings_screen(call.message, state, session, call.from_user.id)


@router.message(ProfileSettingsStates.waiting_full_name)
async def profile_full_name_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        await state.set_state(None)
        return
    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Введите ФИО в формате: Фамилия Имя Отчество")
        return
    ok = await update_student_full_name(session, user.student_id, last, first, middle)
    await state.set_state(None)
    if not ok:
        await message.answer("Не удалось обновить ФИО.")
        return
    await _show_settings_screen(message, state, session, message.from_user.id)


@router.message(ProfileSettingsStates.waiting_group)
async def profile_group_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id or not user.student:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        await state.set_state(None)
        return
    current_group = await get_student_group(session, user.student_id)
    if not current_group or not current_group.faculty:
        await message.answer("Не удалось определить текущий факультет.")
        return
    new_group_name = normalize_valid_group_name(message.text or "")
    if not new_group_name:
        await message.answer(get_group_validation_error_text())
        return
    new_group = await get_or_create_group(session, new_group_name, current_group.faculty_id)
    await reassign_student_group(session, user.student_id, new_group.id)
    await clear_user_manual_notification_subjects_for_group_change(session, user.id)
    await state.set_state(None)
    await _show_settings_screen(message, state, session, message.from_user.id)


@router.message(ProfileSettingsStates.waiting_faculty)
async def profile_faculty_message(message: Message, state: FSMContext):
    faculty_name = normalize_faculty_name(message.text or "")
    if not faculty_name:
        await message.answer("Введите непустое название факультета.")
        return
    await state.update_data(profile_pending_faculty=faculty_name)
    await state.set_state(ProfileSettingsStates.waiting_group_after_faculty)
    data = await state.get_data()
    await _render_screen(
        message,
        state,
        "Введите новую группу для выбранного факультета.",
        profile_cancel_edit_kb(),
        edit_message_id=data.get("profile_screen_message_id"),
    )


@router.message(ProfileSettingsStates.waiting_group_after_faculty)
async def profile_group_after_faculty_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        await state.set_state(None)
        return
    data = await state.get_data()
    faculty_name = data.get("profile_pending_faculty")
    if not faculty_name:
        await message.answer("Не удалось определить факультет. Начните снова из настроек.")
        await state.set_state(None)
        return
    group_name = normalize_valid_group_name(message.text or "")
    if not group_name:
        await message.answer(get_group_validation_error_text())
        return
    faculty = await get_or_create_faculty(session, faculty_name)
    group = await get_or_create_group(session, group_name, faculty.id)
    await reassign_student_group(session, user.student_id, group.id)
    await clear_user_manual_notification_subjects_for_group_change(session, user.id)
    await state.update_data(profile_pending_faculty=None)
    await state.set_state(None)
    await _show_settings_screen(message, state, session, message.from_user.id)
