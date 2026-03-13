from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.admin import admin_groups_kb, admin_users_kb
from bot.keyboards.callbacks import AdminPanelCallback
from bot.keyboards.common import (
    ADMIN_ALIASES,
    ADMIN_BROADCAST_ALIASES,
    ADMIN_GROUPS_ALIASES,
    ADMIN_USERS_ALIASES,
    STUDENT_MODE_ALIASES,
    main_menu_kb,
)
from bot.services.groups import list_groups
from bot.services.users import (
    get_user_by_tg,
    is_admin_mode,
    is_admin_user,
    is_starosta_user,
    list_registered_users,
    set_admin_group,
    set_admin_mode,
)
from bot.states.admin_panel import AdminPanelStates

router = Router()
PAGE_SIZE = 10


def _admin_mode_text(user) -> str:
    selected_group = user.admin_group.name if user and user.admin_group else "не выбрана"
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


@router.message(F.text.in_(ADMIN_ALIASES))
async def open_admin_mode(message: Message, state: FSMContext, session: AsyncSession):
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
async def admin_groups(message: Message, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return
    await show_groups(message, session, page=1, edit=False)


@router.message(F.text.in_(ADMIN_USERS_ALIASES))
async def admin_users(message: Message, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return
    await show_registered_users(message, session, page=1, edit=False)


@router.message(F.text.in_(ADMIN_BROADCAST_ALIASES))
async def start_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        return

    await state.set_state(AdminPanelStates.waiting_broadcast_text)
    await message.answer("Введите текст рассылки для всех зарегистрированных пользователей.")


@router.callback_query(AdminPanelCallback.filter())
async def admin_callbacks(call: CallbackQuery, callback_data: AdminPanelCallback, session: AsyncSession):
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
    if action == "groups_page":
        await show_groups(call.message, session, page=int(callback_data.value), edit=True)
        return
    if action == "users_page":
        await show_registered_users(call.message, session, page=int(callback_data.value), edit=True)
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
                f"Выбрана группа {group.name}.\n"
                "Теперь можно открывать «Староста», «Расписание» и «Список группы» для этой группы."
            ),
            None,
            edit=True,
        )
        return


@router.message(AdminPanelStates.waiting_broadcast_text)
async def broadcast_message(message: Message, state: FSMContext, session: AsyncSession):
    user = await _require_admin(session, message.from_user.id)
    if not user:
        await message.answer("Сначала включите режим администратора.")
        await state.clear()
        return

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
    items = [(group.id, f"{group.name} • {group.faculty.name}") for group in groups[start:end]]
    text = f"Выберите группу\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, admin_groups_kb(items, page, total_pages), edit)


async def show_registered_users(message: Message, session: AsyncSession, page: int, edit: bool):
    users = await list_registered_users(session)
    total_pages = max(1, (len(users) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    items: list[tuple[int, str]] = []
    for user in users[start:end]:
        group_name = user.student.group.name if user.student and user.student.group else "—"
        role_label = "староста" if is_starosta_user(user) else "студент"
        admin_label = " + admin" if is_admin_user(user) else ""
        items.append((user.id, f"{user.tg_id} | {role_label}{admin_label} | {group_name}"))
    text = f"Все зарегистрированные пользователи\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, admin_users_kb(items, page, total_pages), edit)


async def _safe_edit_or_answer(message: Message, text: str, reply_markup, edit: bool):
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup)
