from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import (
    BACK_ALIASES,
    LABS_ALIASES,
    PRACTICE_ALIASES,
    PRIORITY_ALIASES,
    main_menu_kb,
    subjects_kb,
    subject_back_kb,
    subject_view_kb,
    admin_add_subject_kind_kb,
    sort_kb,
    works_kb,
    students_paginated_kb,
    admin_remove_works_kb,
    confirm_kb,
    score_optional_kb,
)
from bot.keyboards.callbacks import (
    SubjectCallback,
    ActionCallback,
    SortCallback,
    WorkCallback,
    SubjectWorkActionCallback,
    StudentCallback,
    PageCallback,
    AdminWorkCallback,
    ConfirmCallback,
    AddSubjectCallback,
)
from bot.models import Role, SubjectKind
from bot.services.priority import get_priority_list
from bot.services.students import get_student_group
from bot.services.subjects import (
    list_group_subjects,
    list_active_work_numbers,
    get_group_subject,
    add_work_number,
    deactivate_work_number,
    create_subject_with_works,
)
from bot.services.submissions import (
    delete_submission,
    list_group_students,
    list_submitted_numbers,
    submissions_map,
    submit_work,
    get_submission_details,
    is_work_submitted,
)
from bot.services.users import get_effective_group, get_user_by_tg, is_admin_mode, is_admin_user
from bot.states.admin import AdminStates
from bot.states.subject import SubjectStates
from bot.utils.names import format_full_name, format_short_name
from bot.utils.render import render_progress_bar, render_work_row, score_to_grade

router = Router()
PAGE_SIZE = 5
TEXT_LIMIT = 3800


async def _student_can_use_subject_actions(session: AsyncSession, user, group_subject_id: int) -> bool:
    if not user or not user.student_id:
        return False
    student_group = await get_student_group(session, user.student_id)
    group_subject = await get_group_subject(session, group_subject_id)
    return bool(student_group and group_subject and student_group.id == group_subject.group_id)


async def _answer_chunked(message: Message, blocks: list[str]) -> None:
    chunk: list[str] = []
    current_length = 0
    for block in blocks:
        block_length = len(block) + (2 if chunk else 0)
        if chunk and current_length + block_length > TEXT_LIMIT:
            await message.answer("\n\n".join(chunk).strip())
            chunk = [block]
            current_length = len(block)
            continue
        chunk.append(block)
        current_length += block_length
    if chunk:
        await message.answer("\n\n".join(chunk).strip())


def _build_priority_blocks(items: list[dict]) -> list[str]:
    blocks = ["📊 Очередность сдачи\nЧем выше приоритет, тем раньше студенту стоит идти на сдачу."]
    for idx, item in enumerate(items, start=1):
        if item["is_inactive"]:
            blocks.append(f"🟥 {item['short_name']} — неактивен")
            continue
        badge = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}.get(idx, f"{idx}.")
        blocks.append(
            f"{badge} {item['short_name']} {render_progress_bar(item['completed'], item['total'])} "
            f"{item['completed']}/{item['total']} • {item['priority'] * 100:.2f}%"
        )
    return blocks


async def _delete_message_by_id(message: Message, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
    except Exception:
        pass


async def _update_subject_screen(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup,
    *,
    force_new: bool = False,
) -> None:
    data = await state.get_data()
    screen_message_id = data.get("subject_screen_message_id")
    if not force_new and screen_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=screen_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                return
        except Exception:
            pass

    screen_message = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(subject_screen_message_id=screen_message.message_id)


async def _close_subject_ui(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _delete_message_by_id(message, data.get("subject_picker_message_id"))
    await _delete_message_by_id(message, data.get("subject_screen_message_id"))
    await state.update_data(
        subject_picker_message_id=None,
        subject_screen_message_id=None,
        group_subject_id=None,
        subject_mode=None,
    )


@router.message(F.text.in_(LABS_ALIASES))
async def labs_handler(message: Message, session: AsyncSession, state: FSMContext):
    await show_subjects(message, session, state, SubjectKind.LAB)


@router.message(F.text.in_(PRACTICE_ALIASES))
async def practice_handler(message: Message, session: AsyncSession, state: FSMContext):
    await show_subjects(message, session, state, SubjectKind.PRACTICE)


async def show_subjects(message: Message, session: AsyncSession, state: FSMContext, kind: SubjectKind):
    await clear_score_prompt(message, state)
    await _close_subject_ui(message, state)
    await show_subject_picker(message, session, state, kind, tg_user_id=message.from_user.id)


async def show_subject_picker(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    kind: SubjectKind,
    *,
    edit_current: bool = False,
    tg_user_id: int | None = None,
):
    user = await get_user_by_tg(session, tg_user_id or message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Группа не найдена. Если вы админ, сначала выберите группу через «Админ».")
        return

    items = []
    group_subjects = await list_group_subjects(session, group.id, kind)
    for gs in group_subjects:
        items.append((gs.id, gs.subject.name, gs.subject.kind))

    if not items:
        await message.answer("Дисциплины не настроены для вашей группы.")
        return

    text = (
        "Выберите дисциплину из списка ниже.\n"
        "После выбора откроется журнал группы и быстрые действия."
    )
    reply_markup = subjects_kb(items)
    await state.update_data(
        kind=kind.value,
        group_subject_id=None,
        subject_mode=None,
    )
    if edit_current:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=text,
                reply_markup=reply_markup,
            )
            await state.update_data(
                subject_picker_message_id=message.message_id,
                subject_screen_message_id=None,
            )
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                await state.update_data(
                    subject_picker_message_id=message.message_id,
                    subject_screen_message_id=None,
                )
                return
        except Exception:
            pass

    picker_message = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(
        subject_picker_message_id=picker_message.message_id,
        subject_screen_message_id=None,
    )


@router.callback_query(SubjectCallback.filter())
async def subject_selected(call: CallbackQuery, callback_data: SubjectCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    await state.update_data(
        group_subject_id=callback_data.group_subject_id,
        sort="alpha",
        page_subject=1,
        subject_picker_message_id=call.message.message_id,
        subject_screen_message_id=call.message.message_id,
        subject_mode="dashboard",
    )
    await show_subject_view(call.message, session, state)
    await state.set_state(SubjectStates.viewing_subject)


async def show_subject_view(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    force_new: bool = False,
):
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await message.answer("Сначала выберите дисциплину.")
        return

    gs = await get_group_subject(session, group_subject_id)
    if not gs:
        await message.answer("Дисциплина не найдена.")
        return

    active_numbers = await list_active_work_numbers(session, group_subject_id)
    total = len(active_numbers)
    subs_map = await submissions_map(session, group_subject_id)
    students = await list_group_students(session, gs.group_id)

    sort_by = data.get("sort", "alpha")
    if sort_by == "count":
        students.sort(
            key=lambda s: (
                s.is_inactive,
                -len(subs_map.get(s.id, [])),
                s.last_name,
                s.first_name,
                s.middle_name or "",
            )
        )
    else:
        students.sort(key=lambda s: (s.is_inactive, s.last_name, s.first_name, s.middle_name or ""))

    total_students = len(students)
    total_pages = max(1, (total_students + PAGE_SIZE - 1) // PAGE_SIZE)
    page = int(data.get("page_subject", 1))
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    await state.update_data(page_subject=page)

    lines = [
        f"📘 Дисциплина: {gs.subject.name}",
        f"👥 Студентов: {total_students} | Работ: {total}",
        f"📄 Страница {page}/{total_pages}",
        "",
    ]
    if students[start:end]:
        for idx, student in enumerate(students[start:end], start=start + 1):
            short_name = format_short_name(student.last_name, student.first_name, student.middle_name)
            if student.is_inactive:
                lines.append(f"{idx}. {short_name} 🟥")
                continue
            submitted = subs_map.get(student.id, [])
            lines.append(f"{idx}. {short_name} — {len(submitted)}/{total}")
            lines.append(render_work_row(active_numbers, submitted))
    else:
        lines.append("В группе пока нет студентов.")
    lines.append("")
    lines.append(f"🟩 — сдано\n"
                 "1️⃣ — номер несданной работы\n"
                 "🟥 — неактивный студент")

    text = "\n".join(lines)
    await state.update_data(subject_mode="dashboard")
    await _update_subject_screen(
        message,
        state,
        text,
        subject_view_kb(page, total_pages),
        force_new=force_new,
    )


@router.callback_query(ActionCallback.filter(F.name == "sort"))
async def sort_action(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.update_data(subject_mode="sort")
    await _update_subject_screen(call.message, state, "Выберите способ сортировки списка:", sort_kb())


@router.callback_query(SortCallback.filter())
async def apply_sort(call: CallbackQuery, callback_data: SortCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(sort=callback_data.by)
    await show_subject_view(call.message, session, state)


@router.callback_query(PageCallback.filter(F.action == "subject"))
async def subject_page(call: CallbackQuery, callback_data: PageCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(page_subject=callback_data.page)
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "mark"))
async def mark_action(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return

    user = await get_user_by_tg(session, call.from_user.id)
    if not user or not user.student_id:
        await call.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    if not await _student_can_use_subject_actions(session, user, int(group_subject_id)):
        await call.message.answer("Свои сдачи доступны только для вашей группы. Для чужой группы используйте режим «Староста».")
        return

    await clear_score_prompt(call.message, state)
    await state.update_data(mark_for_student=user.student_id)
    await show_work_selection(call.message, session, state)
    await state.set_state(SubjectStates.marking_work)


@router.callback_query(StudentCallback.filter())
async def mark_select_student(call: CallbackQuery, callback_data: StudentCallback, session: AsyncSession, state: FSMContext):
    await call.answer("Через эту кнопку отмечаются только ваши работы. Для группы используйте раздел «Староста».", show_alert=True)


@router.callback_query(PageCallback.filter(F.action == "mark"))
async def mark_page(call: CallbackQuery, callback_data: PageCallback, session: AsyncSession, state: FSMContext):
    await call.answer("Для отметки других студентов используйте раздел «Староста».", show_alert=True)


@router.callback_query(WorkCallback.filter())
async def mark_work_number(call: CallbackQuery, callback_data: WorkCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    student_id = data.get("mark_for_student")
    if not all([group_subject_id, student_id]):
        await call.message.answer("Ошибка состояния. Начните снова.")
        await state.clear()
        return

    if await is_work_submitted(session, student_id, group_subject_id, callback_data.number):
        await call.answer("Эта работа уже отмечена. Отмена невозможна.", show_alert=True)
        return

    await clear_score_prompt(call.message, state)
    await state.update_data(work_number=callback_data.number)
    prompt = await call.message.answer(
        "Введите балл от 0 до 100.\n"
        "Или нажмите «Без балла».",
        reply_markup=score_optional_kb(),
    )
    await state.update_data(score_prompt_message_id=prompt.message_id)
    await state.set_state(SubjectStates.entering_score)


@router.callback_query(SubjectWorkActionCallback.filter(F.action == "delete"))
async def delete_marked_work(call: CallbackQuery, callback_data: SubjectWorkActionCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    student_id = data.get("mark_for_student")
    if not all([group_subject_id, student_id]):
        await call.message.answer("Ошибка состояния. Начните снова.")
        await state.clear()
        return

    ok = await delete_submission(session, int(student_id), int(group_subject_id), callback_data.number)
    if not ok:
        await call.answer("Сдача уже отменена.", show_alert=True)
    await refresh_submission_ui(call.message, session, state)


@router.message(SubjectStates.entering_score)
async def enter_score(message: Message, session: AsyncSession, state: FSMContext):
    try:
        score = int(message.text)
    except ValueError:
        await message.answer("Введите число от 0 до 100.")
        return
    if score < 0 or score > 100:
        await message.answer("Балл должен быть от 0 до 100.")
        return

    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    student_id = data.get("mark_for_student")
    work_number = data.get("work_number")
    if not all([group_subject_id, student_id, work_number]):
        await message.answer("Ошибка состояния. Начните снова.")
        await state.clear()
        return

    ok = await submit_work(session, student_id, group_subject_id, work_number, score)
    if not ok:
        await message.answer("Эта работа уже отмечена. Отмена невозможна.")
        await refresh_submission_ui(message, session, state, cleanup_message=message)
        return

    await refresh_submission_ui(message, session, state, cleanup_message=message)


@router.callback_query(ActionCallback.filter(F.name == "stats"))
async def my_stats(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or not user.student_id:
        await call.message.answer("Сначала зарегистрируйтесь через /start.")
        return
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    if not await _student_can_use_subject_actions(session, user, int(group_subject_id)):
        await call.message.answer("Моя статистика доступна только для вашей группы. Для других групп используйте админские инструменты.")
        return

    details = await get_submission_details(session, user.student_id, group_subject_id)
    active_numbers = await list_active_work_numbers(session, group_subject_id)
    total = len(active_numbers)
    by_number = {d.work_number: d for d in details}
    lines = ["Ваша статистика:"]
    scores: list[int] = []
    for number in active_numbers:
        if number in by_number:
            if by_number[number].score is None:
                lines.append(f"{number}. Сдано🟩 – без балла")
            else:
                scores.append(by_number[number].score)
                lines.append(f"{number}. Сдано🟩 – Балл {by_number[number].score}")
        else:
            lines.append(f"{number}. Не сдано🟥")
    avg_score = (sum(scores) / len(scores)) if scores else 0
    grade = score_to_grade(avg_score)
    lines.append("")
    lines.append(f"Средний балл: {int(avg_score)}")
    lines.append(f"Оценка: {grade}")
    await state.update_data(subject_mode="stats")
    await _update_subject_screen(call.message, state, "\n".join(lines), subject_back_kb())


@router.callback_query(ActionCallback.filter(F.name == "priority"))
async def priority_action(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    items = await get_priority_list(session, group_subject_id)
    if not items:
        await call.message.answer("Нет данных для очередности.")
        return
    await state.update_data(subject_mode="priority")
    await _update_subject_screen(call.message, state, "\n".join(_build_priority_blocks(items)), subject_back_kb())


@router.callback_query(ActionCallback.filter(F.name == "admin_add_work"))
async def admin_add_work(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    new_number = await add_work_number(session, group_subject_id)
    await call.message.answer(f"Добавлена работа №{new_number}.")
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "admin_remove_work"))
async def admin_remove_work(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    numbers = await list_active_work_numbers(session, group_subject_id)
    if not numbers:
        await call.message.answer("Нет активных работ.")
        return
    await call.message.answer("Выберите номер работы для удаления:", reply_markup=admin_remove_works_kb(numbers))


@router.callback_query(AdminWorkCallback.filter(F.action == "remove_work"))
async def admin_remove_work_confirm(call: CallbackQuery, callback_data: AdminWorkCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    ok = await deactivate_work_number(session, group_subject_id, callback_data.number)
    if ok:
        await call.message.answer("Работа удалена (номер сохранён).")
    else:
        await call.message.answer("Работа не найдена или уже удалена.")
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "admin_remove_subject"))
async def admin_remove_subject(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    await call.message.answer(
        "Удалить дисциплину? Это действие нельзя отменить.",
        reply_markup=confirm_kb("admin_remove_subject", str(group_subject_id)),
    )


@router.callback_query(ConfirmCallback.filter(F.action == "admin_remove_subject"))
async def admin_remove_subject_confirm(call: CallbackQuery, callback_data: ConfirmCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    if callback_data.value == "no":
        await call.message.answer("Отменено.")
        return
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    gs = await get_group_subject(session, int(callback_data.value))
    if not gs:
        await call.message.answer("Дисциплина не найдена.")
        return
    gs.is_active = False
    await session.commit()
    await call.message.answer("Дисциплина удалена.")
    await state.clear()


@router.message(F.text.in_(PRIORITY_ALIASES))
async def priority_list(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await message.answer("Сначала выберите дисциплину.")
        return
    items = await get_priority_list(session, group_subject_id)
    if not items:
        await message.answer("Нет данных для очередности.")
        return
    await _answer_chunked(message, _build_priority_blocks(items))


async def _return_to_main_menu(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    *,
    tg_user_id: int | None = None,
) -> None:
    await clear_score_prompt(message, state)
    await _close_subject_ui(message, state)
    await state.clear()
    user = await get_user_by_tg(session, tg_user_id or message.from_user.id)
    is_starosta = bool(user and user.role == Role.STAROSTA.value)
    await message.answer(
        "Главное меню. Выберите раздел:",
        reply_markup=main_menu_kb(
            is_starosta=is_starosta,
            is_admin=is_admin_user(user),
            admin_mode=is_admin_mode(user),
        ),
    )


@router.message(F.text.in_(BACK_ALIASES))
async def back_to_menu(message: Message, state: FSMContext, session: AsyncSession):
    await _return_to_main_menu(message, state, session, tg_user_id=message.from_user.id)


@router.callback_query(ActionCallback.filter(F.name == "subject_menu"))
async def subject_menu(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await _return_to_main_menu(call.message, state, session, tg_user_id=call.from_user.id)


@router.callback_query(ActionCallback.filter(F.name == "subject_list"))
async def subject_list(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    data = await state.get_data()
    kind_value = data.get("kind")
    if not kind_value:
        await call.answer("Список дисциплин недоступен.", show_alert=True)
        return
    await show_subject_picker(
        call.message,
        session,
        state,
        SubjectKind(kind_value),
        edit_current=True,
        tg_user_id=call.from_user.id,
    )
    await state.set_state(SubjectStates.viewing_subject)


@router.callback_query(ActionCallback.filter(F.name == "noop"))
async def noop_callback(call: CallbackQuery):
    await call.answer()


@router.callback_query(ActionCallback.filter(F.name == "work_back"))
async def work_back(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "mark_back"))
async def mark_back(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "subject_back"))
async def subject_back(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "no_score"))
async def no_score_submit(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    student_id = data.get("mark_for_student")
    work_number = data.get("work_number")
    if not all([group_subject_id, student_id, work_number]):
        await call.message.answer("Ошибка состояния. Начните снова.")
        await state.clear()
        return
    ok = await submit_work(session, student_id, group_subject_id, work_number, None)
    if not ok:
        await call.message.answer("Эта работа уже отмечена. Отмена невозможна.")
        await refresh_submission_ui(call.message, session, state)
        return
    await refresh_submission_ui(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "cancel_score"))
async def cancel_score_submit(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await clear_score_prompt(call.message, state)
    await show_work_selection(call.message, session, state)
    await state.set_state(SubjectStates.marking_work)


async def show_work_selection(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    student_id = data.get("mark_for_student")
    if not all([group_subject_id, student_id]):
        await message.answer("Сначала выберите дисциплину.")
        return

    numbers = await list_active_work_numbers(session, group_subject_id)
    if not numbers:
        await message.answer("Для этой дисциплины пока нет активных работ.")
        return

    submitted_numbers = await list_submitted_numbers(session, student_id, group_subject_id)
    text = "Выберите номер работы для отметки:\n🟩 — работа уже отмечена, нажатие удалит сдачу."
    reply_markup = works_kb(numbers, submitted_numbers)
    await state.update_data(
        subject_mode="mark",
        mark_group_subject_id=group_subject_id,
        mark_student_id=student_id,
    )
    await _update_subject_screen(message, state, text, reply_markup)


async def clear_score_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    prompt_message_id = data.get("score_prompt_message_id")
    await _delete_message_by_id(message, prompt_message_id)
    await state.update_data(score_prompt_message_id=None, work_number=None)


async def refresh_submission_ui(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    cleanup_message: Message | None = None,
):
    await clear_score_prompt(message, state)
    if cleanup_message:
        try:
            await cleanup_message.delete()
        except Exception:
            pass
    await show_work_selection(message, session, state)
    await state.set_state(SubjectStates.marking_work)


async def show_student_selection(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await message.answer("Сначала выберите дисциплину.")
        return
    gs = await get_group_subject(session, group_subject_id)
    students = await list_group_students(session, gs.group_id)
    total_students = len(students)
    total_pages = max(1, (total_students + PAGE_SIZE - 1) // PAGE_SIZE)
    page = int(data.get("page_mark", 1))
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    items = [
        (s.id, format_full_name(s.last_name, s.first_name, s.middle_name))
        for s in students[start:end]
    ]
    await message.answer(
        "Выберите студента для отметки:",
        reply_markup=students_paginated_kb(items, "mark", page, total_pages),
    )


@router.callback_query(ActionCallback.filter(F.name == "admin_add_subject"))
async def admin_add_subject_start(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await call.message.answer("Доступно только старосте.")
        return
    await call.message.answer("Выберите тип дисциплины:", reply_markup=admin_add_subject_kind_kb())


@router.callback_query(AddSubjectCallback.filter())
async def admin_add_subject_kind(call: CallbackQuery, callback_data: AddSubjectCallback, state: FSMContext):
    await call.answer()
    await state.update_data(add_subject_kind=callback_data.kind)
    await call.message.answer("Введите название дисциплины:")
    await state.set_state(AdminStates.waiting_add_subject_name)


@router.message(AdminStates.waiting_add_subject_name)
async def admin_add_subject_name(message: Message, state: FSMContext):
    await state.update_data(add_subject_name=message.text.strip())
    await message.answer("Введите количество работ (число):")
    await state.set_state(AdminStates.waiting_add_subject_count)


@router.message(AdminStates.waiting_add_subject_count)
async def admin_add_subject_count(message: Message, session: AsyncSession, state: FSMContext):
    try:
        count = int(message.text)
    except ValueError:
        await message.answer("Количество работ должно быть числом.")
        return
    if count <= 0:
        await message.answer("Количество должно быть больше 0.")
        return

    data = await state.get_data()
    kind = data.get("add_subject_kind")
    name = data.get("add_subject_name")
    group_subject_id = data.get("group_subject_id")
    if not all([kind, name, group_subject_id]):
        await message.answer("Недостаточно данных. Начните снова.")
        await state.clear()
        return

    gs = await get_group_subject(session, group_subject_id)
    if not gs:
        await message.answer("Группа не найдена.")
        await state.clear()
        return

    subject_kind = SubjectKind.LAB if kind == "lab" else SubjectKind.PRACTICE
    await create_subject_with_works(session, gs.group_id, name, subject_kind, count)
    await message.answer("Дисциплина добавлена.")
    await state.set_state(SubjectStates.viewing_subject)
