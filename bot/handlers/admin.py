from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.admin import (
    admin_broadcast_kb,
    admin_groups_kb,
    admin_user_card_kb,
    admin_user_groups_kb,
    admin_user_role_kb,
    admin_users_kb,
)
from bot.keyboards.callbacks import AdminPanelCallback, ConfirmCallback
from bot.keyboards.common import (
    ADMIN_ALIASES,
    ADMIN_BROADCAST_ALIASES,
    ADMIN_GROUPS_ALIASES,
    ADMIN_USERS_ALIASES,
    GROUP_LIST_ALIASES,
    SCHEDULE_ALIASES,
    STAROSTA_ALIASES,
    STUDENT_MODE_ALIASES,
    confirm_kb,
    main_menu_kb,
)
from bot.models import Role
from bot.services.admin_panel import (
    delete_student_with_related,
    reassign_student_group,
    set_role_for_student_user,
    update_student_full_name,
)
from bot.services.groups import list_groups
from bot.services.users import (
    get_user_by_id,
    get_user_by_tg,
    is_admin_mode,
    is_admin_user,
    is_starosta_user,
    list_registered_users,
    set_admin_group,
    set_admin_mode,
)
from bot.states.admin_panel import AdminPanelStates
from bot.utils.admin_state import cancel_admin_broadcast_flow
from bot.utils.names import format_full_name, format_short_name, normalize_group_name, split_full_name

router = Router()
PAGE_SIZE = 10


def _admin_mode_text(user) -> str:
    selected_group = normalize_group_name(user.admin_group.name) if user and user.admin_group else "не выбрана"
    return (
        "Режим администратора включен.\n"
        f"Текущая выбранная группа: {selected_group}.\n"
        "Используйте кнопки ниже для управления."
    )


async def _require_admin(session: AsyncSession, tg_id: int, require_mode: bool = True):
    user = await get_user_by_tg(session, tg_id)
    if not is_admin_user(user):
        return None
    if require_mode and not is_admin_mode(user):
        return None
    return user


def _student_menu(user):
    return main_menu_kb(
        is_starosta=is_starosta_user(user),
        is_admin=is_admin_user(user),
        admin_mode=False,
    )


async def _delete_message_by_id(message: Message, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
    except Exception:
        pass


@router.message(F.text.in_(ADMIN_ALIASES))
async def open_admin_mode(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    if not is_admin_user(user):
        await message.answer("Раздел доступен только админу.")
        return

    await state.clear()
    await set_admin_mode(session, user, True)
    user = await get_user_by_tg(session, message.from_user.id)
    await message.answer(
        _admin_mode_text(user),
        reply_markup=main_menu_kb(is_admin=True, admin_mode=True),
    )


@router.message(F.text.in_(STUDENT_MODE_ALIASES))
async def close_admin_mode(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await get_user_by_tg(session, message.from_user.id)
    if not is_admin_user(user):
        await message.answer("Эта кнопка доступна только админу.")
        return

    await state.clear()
    await set_admin_mode(session, user, False)
    user = await get_user_by_tg(session, message.from_user.id)
    await message.answer(
        "Режим студента активирован.",
        reply_markup=_student_menu(user),
    )


@router.message(F.text.in_(ADMIN_GROUPS_ALIASES))
async def admin_groups(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return
    await show_groups(message, session, page=1, edit=False)


@router.message(F.text.in_(ADMIN_USERS_ALIASES))
async def admin_users(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return
    await show_registered_users(message, session, state, page=1, edit=False)


@router.message(F.text.in_(ADMIN_BROADCAST_ALIASES))
async def start_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return

    await state.set_state(AdminPanelStates.waiting_broadcast_text)
    prompt = await message.answer(
        "Введите текст рассылки для всех зарегистрированных пользователей.",
        reply_markup=admin_broadcast_kb(),
    )
    await state.update_data(admin_broadcast_prompt_message_id=prompt.message_id)


@router.callback_query(AdminPanelCallback.filter())
async def admin_callbacks(call: CallbackQuery, callback_data: AdminPanelCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    user = await _require_admin(session, call.from_user.id)
    if not user:
        await call.message.answer("Сначала включите режим администратора.")
        return

    action = callback_data.action
    if action == "noop":
        return
    if action == "back":
        await _safe_edit_or_answer(call.message, _admin_mode_text(user), None, edit=True)
        return
    if action == "broadcast_cancel":
        await state.clear()
        await _safe_edit_or_answer(call.message, "Рассылка отменена.", None, edit=True)
        return
    if action == "broadcast_menu":
        await state.clear()
        await _safe_edit_or_answer(call.message, _admin_mode_text(user), None, edit=True)
        return
    if action == "groups_page":
        await show_groups(call.message, session, page=int(callback_data.value), edit=True)
        return
    if action == "users_page":
        await show_registered_users(call.message, session, state, page=int(callback_data.value), edit=True)
        return
    if action == "select_group":
        groups = await list_groups(session)
        group = next((item for item in groups if item.id == int(callback_data.value)), None)
        if not group:
            await call.message.answer("Группа не найдена.")
            return
        user = await set_admin_group(session, user, group.id)
        await _safe_edit_or_answer(
            call.message,
            (
                f"Выбрана группа {normalize_group_name(group.name)}.\n"
                "Теперь можно открывать «Староста», «Расписание» и «Список группы» для этой группы."
            ),
            None,
            edit=True,
        )
        return
    if action == "user_view":
        await state.update_data(admin_selected_user_id=int(callback_data.value))
        await show_registered_user_card(call.message, session, int(callback_data.value), edit=True)
        return
    if action == "user_back":
        page = int((await state.get_data()).get("admin_users_page", 1))
        await show_registered_users(call.message, session, state, page=page, edit=True)
        return
    if action == "user_rename":
        await state.update_data(admin_selected_user_id=int(callback_data.value))
        await state.set_state(AdminPanelStates.waiting_user_full_name)
        await call.message.answer("Введите новое ФИО пользователя.")
        return
    if action == "user_role":
        target = await get_user_by_id(session, int(callback_data.value))
        if not target or not target.student_id:
            await call.message.answer("Пользователь не найден.")
            return
        await call.message.edit_text(
            "Выберите роль пользователя:",
            reply_markup=admin_user_role_kb(target.id, target.role),
        )
        return
    if action == "user_set_role":
        user_id_str, role_value = callback_data.value.split(":", maxsplit=1)
        target = await get_user_by_id(session, int(user_id_str))
        if not target or not target.student_id:
            await call.message.answer("Пользователь не найден.")
            return
        role = Role.STAROSTA if role_value == Role.STAROSTA.value else Role.STUDENT
        ok, text = await set_role_for_student_user(session, target.student_id, role)
        if not ok:
            await call.message.answer(text)
            return
        await show_registered_user_card(call.message, session, target.id, edit=True, flash_text=text)
        return
    if action == "user_group":
        target = await get_user_by_id(session, int(callback_data.value))
        if not target or not target.student_id:
            await call.message.answer("Пользователь не найден.")
            return
        await state.update_data(admin_selected_user_id=target.id, admin_user_groups_page=1)
        await show_admin_user_groups(call.message, session, target.id, page=1, edit=True)
        return
    if action == "user_groups_page":
        data = await state.get_data()
        target_user_id = data.get("admin_selected_user_id")
        if not target_user_id:
            await call.message.answer("Сначала выберите пользователя.")
            return
        await show_admin_user_groups(call.message, session, int(target_user_id), page=int(callback_data.value), edit=True)
        return
    if action == "user_pick_group":
        user_id_str, group_id_str = callback_data.value.split(":", maxsplit=1)
        target = await get_user_by_id(session, int(user_id_str))
        if not target or not target.student_id:
            await call.message.answer("Пользователь не найден.")
            return
        ok, text = await reassign_student_group(session, target.student_id, int(group_id_str))
        await show_registered_user_card(call.message, session, target.id, edit=True, flash_text=text if ok else text)
        return
    if action == "user_delete":
        target = await get_user_by_id(session, int(callback_data.value))
        if not target:
            await call.message.answer("Пользователь не найден.")
            return
        if target.tg_id == call.from_user.id:
            await call.message.answer("Нельзя удалить самого себя из админского режима.")
            return
        title = _user_list_label(target)
        await call.message.answer(
            f"Удалить пользователя {title}?",
            reply_markup=confirm_kb("admin_delete_user", str(target.id)),
        )
        return


@router.callback_query(ConfirmCallback.filter(F.action == "admin_delete_user"))
async def confirm_delete_user(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if callback_data.value == "no":
        user_id = (await state.get_data()).get("admin_selected_user_id")
        if user_id:
            await show_registered_user_card(call.message, session, int(user_id), edit=True)
        return

    target = await get_user_by_id(session, int(callback_data.value))
    if not target or not target.student_id:
        await call.message.answer("Пользователь не найден.")
        return
    ok = await delete_student_with_related(session, target.student_id)
    page = int((await state.get_data()).get("admin_users_page", 1))
    if ok:
        await call.message.answer("Пользователь удален.")
    else:
        await call.message.answer("Не удалось удалить пользователя.")
    await show_registered_users(call.message, session, state, page=page, edit=True)


@router.message(AdminPanelStates.waiting_user_full_name)
async def rename_user_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        await state.clear()
        return

    target_user_id = (await state.get_data()).get("admin_selected_user_id")
    if not target_user_id:
        await message.answer("Сначала выберите пользователя.")
        await state.clear()
        return

    target = await get_user_by_id(session, int(target_user_id))
    if not target or not target.student_id:
        await message.answer("Пользователь не найден.")
        await state.clear()
        return

    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Неверный формат. Пример: Иванов Иван Иванович")
        return

    ok = await update_student_full_name(session, target.student_id, last, first, middle)
    await state.set_state(None)
    if not ok:
        await message.answer("Не удалось обновить ФИО.")
        return
    await message.answer("ФИО обновлено.")
    await show_registered_user_card(message, session, target.id, edit=False)


@router.message(
    AdminPanelStates.waiting_broadcast_text,
    ~F.text.in_(
        ADMIN_ALIASES
        + ADMIN_GROUPS_ALIASES
        + ADMIN_USERS_ALIASES
        + ADMIN_BROADCAST_ALIASES
        + STUDENT_MODE_ALIASES
        + GROUP_LIST_ALIASES
        + SCHEDULE_ALIASES
        + STAROSTA_ALIASES
    ),
)
async def broadcast_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        await state.clear()
        return

    data = await state.get_data()
    await _delete_message_by_id(message, data.get("admin_broadcast_prompt_message_id"))
    users = await list_registered_users(session)
    success = 0
    failed = 0
    for target in users:
        try:
            await message.bot.send_message(target.tg_id, f"📣 Сообщение от администратора:\n\n{message.text}")
            success += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(f"Рассылка завершена. Успешно: {success}. Ошибок: {failed}.")


async def show_groups(message: Message, session: AsyncSession, page: int, edit: bool):
    groups = await list_groups(session)
    total_pages = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    items = [(group.id, f"{normalize_group_name(group.name)} • {group.faculty.name}") for group in groups[start:end]]
    text = f"Выберите группу\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, admin_groups_kb(items, page, total_pages), edit)


async def show_registered_users(message: Message, session: AsyncSession, state: FSMContext, page: int, edit: bool):
    users = await list_registered_users(session)
    users.sort(key=lambda item: _user_sort_key(item))
    total_pages = max(1, (len(users) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    await state.update_data(admin_users_page=page)
    items = [(user.id, _user_list_label(user)) for user in users[start:end]]
    text = f"Все зарегистрированные пользователи\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, admin_users_kb(items, page, total_pages), edit)


async def show_registered_user_card(
    message: Message,
    session: AsyncSession,
    user_id: int,
    edit: bool,
    flash_text: str | None = None,
):
    target = await get_user_by_id(session, user_id)
    if not target:
        await message.answer("Пользователь не найден.")
        return

    username = f"@{target.username}" if target.username else "без username"
    group_name = normalize_group_name(target.student.group.name) if target.student and target.student.group else "—"
    faculty_name = (
        target.student.group.faculty.name
        if target.student and target.student.group and target.student.group.faculty
        else "—"
    )
    role_label = "Староста" if target.role == Role.STAROSTA.value else "Студент"
    full_name = (
        format_full_name(target.student.last_name, target.student.first_name, target.student.middle_name)
        if target.student
        else "—"
    )
    lines = []
    if flash_text:
        lines.append(flash_text)
        lines.append("")
    lines.extend(
        [
            "Пользователь:",
            f"• Username: {username}",
            f"• ФИО: {full_name}",
            f"• Группа: {group_name}",
            f"• Факультет: {faculty_name}",
            f"• Роль: {role_label}",
            f"• Права админа: {'да' if is_admin_user(target) else 'нет'}",
        ]
    )
    await _safe_edit_or_answer(message, "\n".join(lines), admin_user_card_kb(target.id), edit)


async def show_admin_user_groups(message: Message, session: AsyncSession, user_id: int, page: int, edit: bool):
    groups = await list_groups(session)
    total_pages = max(1, (len(groups) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    items = [(group.id, f"{normalize_group_name(group.name)} • {group.faculty.name}") for group in groups[start:end]]
    text = f"Выберите группу для пользователя\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, admin_user_groups_kb(items, user_id, page, total_pages), edit)


def _user_list_label(user) -> str:
    username = f"@{user.username}" if user.username else "без username"
    short_name = (
        format_short_name(user.student.last_name, user.student.first_name, user.student.middle_name)
        if user.student
        else "Без ФИО"
    )
    group_name = normalize_group_name(user.student.group.name) if user.student and user.student.group else "—"
    return f"{username} | {short_name} | {group_name}"


def _user_sort_key(user) -> tuple[str, str, str]:
    if not user.student:
        return "", "", ""
    return (
        user.student.last_name,
        user.student.first_name,
        user.student.middle_name or "",
    )


async def _safe_edit_or_answer(message: Message, text: str, reply_markup, edit: bool):
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup)
