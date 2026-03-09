from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import (
    ConfirmCallback,
    StarostaMenuCallback,
    StarostaPageCallback,
    StarostaRoleCallback,
    StarostaStudentCallback,
    StarostaSubjectCallback,
    StarostaWorkCallback,
)
from bot.keyboards.common import STAROSTA_ALIASES, main_menu_kb
from bot.keyboards.starosta import (
    starosta_delete_subject_confirm_kb,
    starosta_delete_user_confirm_kb,
    starosta_main_kb,
    starosta_remove_work_kb,
    starosta_role_kb,
    starosta_students_list_kb,
    starosta_subject_edit_kb,
    starosta_subject_kind_kb,
    starosta_subjects_list_kb,
    starosta_subjects_menu_kb,
    starosta_user_edit_kb,
    starosta_users_menu_kb,
)
from bot.models import Role, SubjectKind
from bot.services.admin_panel import (
    add_student_to_group,
    deactivate_group_subject,
    delete_student_with_related,
    get_group_subject_active,
    get_student_with_user,
    list_group_students_with_user,
    list_group_subjects_all,
    rename_group_subject,
    set_group_subject_kind,
    set_role_for_student_user,
    update_student_full_name,
)
from bot.services.students import get_student_group
from bot.services.subjects import add_work_number, create_subject_with_works, deactivate_work_number, list_active_work_numbers
from bot.services.users import get_user_by_tg
from bot.states.starosta_panel import StarostaStates
from bot.utils.names import format_full_name, split_full_name

router = Router()
PAGE_SIZE = 7


@router.message(F.text.in_(STAROSTA_ALIASES))
async def open_starosta_panel(message: Message, state: FSMContext, session: AsyncSession):
    context = await _get_starosta_context(session, message.from_user.id)
    if not context:
        await message.answer("Раздел доступен только старосте.")
        return
    await state.clear()
    await state.set_state(StarostaStates.viewing_panel)
    await message.answer(
        "Режим старосты включён.\n"
        "Все изменения выполняются через inline-кнопки ниже.",
        reply_markup=main_menu_kb(is_starosta=True),
    )
    await message.answer("Панель старосты:", reply_markup=starosta_main_kb())


@router.callback_query(StarostaMenuCallback.filter(F.section == "main"))
async def main_menu_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if not await _ensure_starosta_callback(call, session):
        return

    await state.set_state(StarostaStates.viewing_panel)
    if callback_data.action == "subjects":
        await _safe_edit(
            call,
            "Раздел дисциплин.\n"
            "Выберите действие:",
            starosta_subjects_menu_kb(),
        )
        return
    if callback_data.action == "users":
        await _safe_edit(
            call,
            "Раздел пользователей.\n"
            "Выберите действие:",
            starosta_users_menu_kb(),
        )
        return
    if callback_data.action == "exit":
        await state.clear()
        await _safe_edit(call, "Режим старосты выключен.", None)
        await call.message.answer("Главное меню.", reply_markup=main_menu_kb(is_starosta=True))


@router.callback_query(StarostaMenuCallback.filter(F.section == "subjects"))
async def subjects_menu_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context
    await state.set_state(StarostaStates.viewing_panel)

    if callback_data.action == "add":
        await state.update_data(st_next_after_kind="subject_add")
        await _safe_edit(call, "Выберите тип новой дисциплины:", starosta_subject_kind_kb())
        return
    if callback_data.action == "edit":
        await _show_subjects_list(call.message, session, state, group.id, mode="edit", page=1, edit=True)
        return
    if callback_data.action == "delete":
        await _show_subjects_list(call.message, session, state, group.id, mode="delete", page=1, edit=True)
        return
    if callback_data.action == "back":
        await _safe_edit(call, "Панель старосты:", starosta_main_kb())


@router.callback_query(StarostaMenuCallback.filter(F.section == "subject_kind"))
async def subject_kind_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return

    if callback_data.action == "back":
        await _safe_edit(call, "Раздел дисциплин.\nВыберите действие:", starosta_subjects_menu_kb())
        return
    if callback_data.action not in ("lab", "practice"):
        return

    data = await state.get_data()
    next_action = data.get("st_next_after_kind")
    kind = SubjectKind.LAB if callback_data.action == "lab" else SubjectKind.PRACTICE

    if next_action == "subject_add":
        await state.update_data(st_add_subject_kind=kind.value)
        await state.set_state(StarostaStates.waiting_add_subject_name)
        await call.message.answer("Введите название дисциплины:")
        return

    if next_action == "subject_change_kind":
        group_subject_id = data.get("st_selected_subject_id")
        if not group_subject_id:
            await call.message.answer("Не выбрана дисциплина.")
            return
        ok, msg = await set_group_subject_kind(session, int(group_subject_id), kind)
        await call.message.answer(msg)
        if not ok:
            return
        await _show_subject_card(call.message, session, int(group_subject_id), edit=False)


@router.message(StarostaStates.waiting_add_subject_name)
async def add_subject_name(message: Message, state: FSMContext, session: AsyncSession):
    context = await _get_starosta_context(session, message.from_user.id)
    if not context:
        await message.answer("Доступно только старосте.")
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите непустое название дисциплины.")
        return
    await state.update_data(st_add_subject_name=name)
    await state.set_state(StarostaStates.waiting_add_subject_count)
    await message.answer("Введите количество работ (число больше 0):")


@router.message(StarostaStates.waiting_add_subject_count)
async def add_subject_count(message: Message, state: FSMContext, session: AsyncSession):
    context = await _get_starosta_context(session, message.from_user.id)
    if not context:
        await message.answer("Доступно только старосте.")
        await state.clear()
        return
    _, group = context

    try:
        count = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите число.")
        return
    if count <= 0:
        await message.answer("Количество должно быть больше 0.")
        return

    data = await state.get_data()
    kind_value = data.get("st_add_subject_kind")
    name = data.get("st_add_subject_name")
    if not kind_value or not name:
        await message.answer("Недостаточно данных. Начните заново через «Староста».")
        await state.clear()
        return

    kind = SubjectKind.LAB if kind_value == SubjectKind.LAB.value else SubjectKind.PRACTICE
    await create_subject_with_works(session, group.id, name, kind, count)
    await state.set_state(StarostaStates.viewing_panel)
    await message.answer("Дисциплина добавлена.")
    await message.answer("Раздел дисциплин.\nВыберите действие:", reply_markup=starosta_subjects_menu_kb())


@router.callback_query(StarostaPageCallback.filter(F.section == "subjects"))
async def subjects_pagination(call: CallbackQuery, callback_data: StarostaPageCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context
    await _show_subjects_list(
        call.message,
        session,
        state,
        group.id,
        mode=callback_data.mode,
        page=callback_data.page,
        edit=True,
    )


@router.callback_query(StarostaSubjectCallback.filter())
async def subject_selected(call: CallbackQuery, callback_data: StarostaSubjectCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if not await _ensure_starosta_callback(call, session):
        return

    group_subject_id = callback_data.group_subject_id
    if callback_data.mode == "edit":
        await state.update_data(st_selected_subject_id=group_subject_id)
        await _show_subject_card(call.message, session, group_subject_id, edit=True)
        return
    if callback_data.mode == "delete":
        gs = await get_group_subject_active(session, group_subject_id)
        if not gs:
            await call.message.answer("Дисциплина не найдена.")
            return
        await _safe_edit(
            call,
            f"Удалить дисциплину «{gs.subject.name}»?\nЭто действие нельзя отменить.",
            starosta_delete_subject_confirm_kb(group_subject_id),
        )


@router.callback_query(ConfirmCallback.filter(F.action == "st_delete_subject"))
async def delete_subject_confirm(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context

    ok = await deactivate_group_subject(session, int(callback_data.value))
    if ok:
        await call.message.answer("Дисциплина удалена.")
    else:
        await call.message.answer("Не удалось удалить дисциплину.")
    await _show_subjects_list(call.message, session, state, group.id, mode="delete", page=1, edit=False)


@router.callback_query(StarostaMenuCallback.filter(F.section == "subject_edit"))
async def subject_edit_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if not await _ensure_starosta_callback(call, session):
        return

    action = callback_data.action
    if action == "back":
        data = await state.get_data()
        page = int(data.get("st_subject_page", 1))
        group_id = data.get("st_group_id")
        if group_id:
            await _show_subjects_list(call.message, session, state, int(group_id), mode="edit", page=page, edit=True)
        return

    if action.startswith("rename|"):
        group_subject_id = int(action.split("|", maxsplit=1)[1])
        await state.update_data(st_selected_subject_id=group_subject_id)
        await state.set_state(StarostaStates.waiting_rename_subject)
        await call.message.answer("Введите новое название дисциплины:")
        return

    if action.startswith("kind|"):
        group_subject_id = int(action.split("|", maxsplit=1)[1])
        await state.update_data(st_selected_subject_id=group_subject_id, st_next_after_kind="subject_change_kind")
        await _safe_edit(call, "Выберите новый тип дисциплины:", starosta_subject_kind_kb())
        return

    if action.startswith("add_work|"):
        group_subject_id = int(action.split("|", maxsplit=1)[1])
        new_number = await add_work_number(session, group_subject_id)
        await call.message.answer(f"Добавлена работа №{new_number}.")
        await _show_subject_card(call.message, session, group_subject_id, edit=False)
        return

    if action.startswith("remove_work|"):
        group_subject_id = int(action.split("|", maxsplit=1)[1])
        numbers = await list_active_work_numbers(session, group_subject_id)
        if not numbers:
            await call.message.answer("У дисциплины нет активных работ.")
            return
        await _safe_edit(
            call,
            "Выберите номер работы для удаления:",
            starosta_remove_work_kb(numbers, group_subject_id),
        )
        return

    if action.startswith("back_to_subject|"):
        group_subject_id = int(action.split("|", maxsplit=1)[1])
        await _show_subject_card(call.message, session, group_subject_id, edit=True)


@router.message(StarostaStates.waiting_rename_subject)
async def rename_subject_message(message: Message, state: FSMContext, session: AsyncSession):
    if not await _ensure_starosta_message(message, session):
        await state.clear()
        return
    data = await state.get_data()
    group_subject_id = data.get("st_selected_subject_id")
    if not group_subject_id:
        await message.answer("Сначала выберите дисциплину.")
        await state.set_state(StarostaStates.viewing_panel)
        return

    ok, msg = await rename_group_subject(session, int(group_subject_id), (message.text or "").strip())
    await message.answer(msg)
    await state.set_state(StarostaStates.viewing_panel)
    if ok:
        await _show_subject_card(message, session, int(group_subject_id), edit=False)


@router.callback_query(StarostaWorkCallback.filter())
async def remove_work_from_subject(call: CallbackQuery, callback_data: StarostaWorkCallback, session: AsyncSession):
    await call.answer()
    if not await _ensure_starosta_callback(call, session):
        return
    action, group_subject_id_str = callback_data.action.split("|", maxsplit=1)
    if action != "remove":
        return
    group_subject_id = int(group_subject_id_str)
    ok = await deactivate_work_number(session, group_subject_id, callback_data.number)
    if ok:
        await call.message.answer(f"Работа №{callback_data.number} удалена.")
    else:
        await call.message.answer("Не удалось удалить работу.")
    await _show_subject_card(call.message, session, group_subject_id, edit=False)


@router.callback_query(StarostaMenuCallback.filter(F.section == "users"))
async def users_menu_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context
    await state.set_state(StarostaStates.viewing_panel)

    if callback_data.action == "add":
        await state.set_state(StarostaStates.waiting_add_user_full_name)
        await call.message.answer(
            "Введите ФИО нового пользователя в формате:\n"
            "Фамилия Имя Отчество\n"
            "(отчество можно не указывать)."
        )
        return
    if callback_data.action == "edit":
        await _show_users_list(call.message, session, state, group.id, mode="edit", page=1, edit=True)
        return
    if callback_data.action == "delete":
        await _show_users_list(call.message, session, state, group.id, mode="delete", page=1, edit=True)
        return
    if callback_data.action == "back":
        await _safe_edit(call, "Панель старосты:", starosta_main_kb())


@router.message(StarostaStates.waiting_add_user_full_name)
async def add_user_message(message: Message, state: FSMContext, session: AsyncSession):
    context = await _get_starosta_context(session, message.from_user.id)
    if not context:
        await message.answer("Доступно только старосте.")
        await state.clear()
        return
    _, group = context
    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Неверный формат. Пример: Иванов Иван Иванович")
        return

    student = await add_student_to_group(session, group.id, last, first, middle)
    await state.set_state(StarostaStates.viewing_panel)
    await message.answer(
        f"Пользователь добавлен: {format_full_name(student.last_name, student.first_name, student.middle_name)}\n"
        "Telegram-аккаунт привяжется после /start этого пользователя."
    )
    await message.answer("Раздел пользователей.\nВыберите действие:", reply_markup=starosta_users_menu_kb())


@router.callback_query(StarostaPageCallback.filter(F.section == "users"))
async def users_pagination(call: CallbackQuery, callback_data: StarostaPageCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context
    await _show_users_list(
        call.message,
        session,
        state,
        group.id,
        mode=callback_data.mode,
        page=callback_data.page,
        edit=True,
    )


@router.callback_query(StarostaStudentCallback.filter())
async def user_selected(call: CallbackQuery, callback_data: StarostaStudentCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    user, _ = context
    student_id = callback_data.student_id
    if callback_data.mode == "edit":
        await state.update_data(st_selected_student_id=student_id)
        await _show_user_card(call.message, session, student_id, edit=True)
        return
    if callback_data.mode == "delete":
        if user.student_id == student_id:
            await call.message.answer("Нельзя удалить самого себя из режима старосты.")
            return
        student = await get_student_with_user(session, student_id)
        if not student:
            await call.message.answer("Пользователь не найден.")
            return
        full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
        await _safe_edit(
            call,
            f"Удалить пользователя «{full_name}»?\n"
            "Будут удалены его сдачи и привязка Telegram-аккаунта.",
            starosta_delete_user_confirm_kb(student_id),
        )


@router.callback_query(ConfirmCallback.filter(F.action == "st_delete_user"))
async def delete_user_confirm(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    user, group = context

    if user.student_id == int(callback_data.value):
        await call.message.answer("Нельзя удалить самого себя из режима старосты.")
        return

    ok = await delete_student_with_related(session, int(callback_data.value))
    if ok:
        await call.message.answer("Пользователь удалён.")
    else:
        await call.message.answer("Не удалось удалить пользователя.")
    await _show_users_list(call.message, session, state, group.id, mode="delete", page=1, edit=False)


@router.callback_query(StarostaMenuCallback.filter(F.section == "user_edit"))
async def user_edit_actions(call: CallbackQuery, callback_data: StarostaMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    context = await _get_starosta_context(session, call.from_user.id)
    if not context:
        await call.answer("Доступно только старосте.", show_alert=True)
        return
    _, group = context

    action = callback_data.action
    if action == "back":
        page = int((await state.get_data()).get("st_user_page", 1))
        await _show_users_list(call.message, session, state, group.id, mode="edit", page=page, edit=True)
        return
    if action.startswith("back_to_user|"):
        student_id = int(action.split("|", maxsplit=1)[1])
        await _show_user_card(call.message, session, student_id, edit=True)
        return
    if action.startswith("rename|"):
        student_id = int(action.split("|", maxsplit=1)[1])
        await state.update_data(st_selected_student_id=student_id)
        await state.set_state(StarostaStates.waiting_edit_user_full_name)
        await call.message.answer("Введите новое ФИО пользователя:")
        return
    if action.startswith("role|"):
        student_id = int(action.split("|", maxsplit=1)[1])
        student = await get_student_with_user(session, student_id)
        if not student:
            await call.message.answer("Пользователь не найден.")
            return
        current_role = student.user.role if student.user else None
        await _safe_edit(
            call,
            "Выберите роль пользователя:",
            starosta_role_kb(student_id, current_role),
        )
        return
    if action.startswith("delete|"):
        student_id = int(action.split("|", maxsplit=1)[1])
        if context[0].student_id == student_id:
            await call.message.answer("Нельзя удалить самого себя из режима старосты.")
            return
        student = await get_student_with_user(session, student_id)
        if not student:
            await call.message.answer("Пользователь не найден.")
            return
        full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
        await _safe_edit(
            call,
            f"Удалить пользователя «{full_name}»?\n"
            "Будут удалены его сдачи и привязка Telegram-аккаунта.",
            starosta_delete_user_confirm_kb(student_id),
        )


@router.message(StarostaStates.waiting_edit_user_full_name)
async def rename_user_message(message: Message, state: FSMContext, session: AsyncSession):
    if not await _ensure_starosta_message(message, session):
        await state.clear()
        return
    data = await state.get_data()
    student_id = data.get("st_selected_student_id")
    if not student_id:
        await message.answer("Сначала выберите пользователя.")
        await state.set_state(StarostaStates.viewing_panel)
        return

    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Неверный формат. Пример: Иванов Иван Иванович")
        return
    ok = await update_student_full_name(session, int(student_id), last, first, middle)
    await state.set_state(StarostaStates.viewing_panel)
    if not ok:
        await message.answer("Не удалось обновить данные пользователя.")
        return
    await message.answer("ФИО пользователя обновлено.")
    await _show_user_card(message, session, int(student_id), edit=False)


@router.callback_query(StarostaRoleCallback.filter())
async def set_user_role(call: CallbackQuery, callback_data: StarostaRoleCallback, session: AsyncSession):
    await call.answer()
    if not await _ensure_starosta_callback(call, session):
        return
    role = Role.STAROSTA if callback_data.role == Role.STAROSTA.value else Role.STUDENT
    ok, msg = await set_role_for_student_user(session, callback_data.student_id, role)
    await call.message.answer(msg)
    if not ok:
        return
    await _show_user_card(call.message, session, callback_data.student_id, edit=False)


@router.callback_query(StarostaMenuCallback.filter((F.section == "noop") & (F.action == "noop")))
async def noop(call: CallbackQuery):
    await call.answer()


async def _show_subjects_list(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    group_id: int,
    mode: str,
    page: int,
    edit: bool,
) -> None:
    subjects = await list_group_subjects_all(session, group_id)
    total = len(subjects)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    title = "Выберите дисциплину для редактирования:" if mode == "edit" else "Выберите дисциплину для удаления:"
    if not subjects:
        text = "В группе пока нет активных дисциплин."
        kb = starosta_subjects_menu_kb()
    else:
        page_items = [
            (gs.id, f"{gs.subject.name} ({'ЛБ' if gs.subject.kind == SubjectKind.LAB.value else 'ПЗ'})")
            for gs in subjects[start:end]
        ]
        text = f"{title}\nСтраница {page}/{total_pages}"
        kb = starosta_subjects_list_kb(page_items, mode, page, total_pages)

    await state.update_data(st_subject_page=page, st_group_id=group_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


async def _show_subject_card(message: Message, session: AsyncSession, group_subject_id: int, edit: bool) -> None:
    gs = await get_group_subject_active(session, group_subject_id)
    if not gs:
        await message.answer("Дисциплина не найдена.")
        return
    numbers = await list_active_work_numbers(session, group_subject_id)
    kind_text = "Лабораторные" if gs.subject.kind == SubjectKind.LAB.value else "Практические"
    text = (
        f"Дисциплина: {gs.subject.name}\n"
        f"Тип: {kind_text}\n"
        f"Активные работы: {len(numbers)}"
    )
    kb = starosta_subject_edit_kb(group_subject_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


async def _show_users_list(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    group_id: int,
    mode: str,
    page: int,
    edit: bool,
) -> None:
    students = await list_group_students_with_user(session, group_id)
    total = len(students)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    title = "Выберите пользователя для редактирования:" if mode == "edit" else "Выберите пользователя для удаления:"
    if not students:
        text = "В группе пока нет пользователей."
        kb = starosta_users_menu_kb()
    else:
        page_items: list[tuple[int, str]] = []
        for student in students[start:end]:
            full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
            role = student.user.role if student.user else "не зарегистрирован"
            page_items.append((student.id, f"{full_name} [{role}]"))
        text = f"{title}\nСтраница {page}/{total_pages}"
        kb = starosta_students_list_kb(page_items, mode, page, total_pages)

    await state.update_data(st_user_page=page, st_group_id=group_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


async def _show_user_card(message: Message, session: AsyncSession, student_id: int, edit: bool) -> None:
    student = await get_student_with_user(session, student_id)
    if not student:
        await message.answer("Пользователь не найден.")
        return
    full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
    tg_status = f"@{student.user.username}" if student.user and student.user.username else "не привязан"
    role = student.user.role if student.user else "не зарегистрирован"
    text = (
        f"Пользователь: {full_name}\n"
        f"Telegram: {tg_status}\n"
        f"Роль: {role}"
    )
    kb = starosta_user_edit_kb(student_id)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=kb)


async def _safe_edit(call: CallbackQuery, text: str, reply_markup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        await call.message.answer(text, reply_markup=reply_markup)


async def _get_starosta_context(session: AsyncSession, tg_id: int):
    user = await get_user_by_tg(session, tg_id)
    if not user or user.role != Role.STAROSTA.value or not user.student_id:
        return None
    group = await get_student_group(session, user.student_id)
    if not group:
        return None
    return user, group


async def _ensure_starosta_callback(call: CallbackQuery, session: AsyncSession) -> bool:
    context = await _get_starosta_context(session, call.from_user.id)
    if context:
        return True
    await call.answer("Раздел доступен только старосте.", show_alert=True)
    return False


async def _ensure_starosta_message(message: Message, session: AsyncSession) -> bool:
    context = await _get_starosta_context(session, message.from_user.id)
    if context:
        return True
    await message.answer("Раздел доступен только старосте.")
    return False
