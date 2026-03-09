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
    subject_actions_kb,
    subject_inline_actions_kb,
    admin_add_subject_kind_kb,
    sort_kb,
    works_kb,
    pagination_kb,
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
    list_group_students,
    submissions_map,
    submit_work,
    get_submission_details,
    total_active_works,
    is_work_submitted,
)
from bot.services.users import get_user_by_tg
from bot.states.admin import AdminStates
from bot.states.subject import SubjectStates
from bot.utils.names import format_full_name
from bot.utils.render import render_work_row, score_to_grade

router = Router()
PAGE_SIZE = 5


@router.message(F.text.in_(LABS_ALIASES))
async def labs_handler(message: Message, session: AsyncSession, state: FSMContext):
    await show_subjects(message, session, state, SubjectKind.LAB)


@router.message(F.text.in_(PRACTICE_ALIASES))
async def practice_handler(message: Message, session: AsyncSession, state: FSMContext):
    await show_subjects(message, session, state, SubjectKind.PRACTICE)


async def show_subjects(message: Message, session: AsyncSession, state: FSMContext, kind: SubjectKind):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or not user.student_id:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    group = await get_student_group(session, user.student_id)
    if not group:
        await message.answer("Группа не найдена.")
        return

    items = []
    group_subjects = await list_group_subjects(session, group.id, kind)
    for gs in group_subjects:
        items.append((gs.id, gs.subject.name, gs.subject.kind))

    if not items:
        await message.answer("Дисциплины не настроены для вашей группы.")
        return

    await state.update_data(kind=kind.value)
    await message.answer(
        "Выберите дисциплину из списка ниже.\n"
        "После выбора откроется журнал группы и быстрые действия.",
        reply_markup=subjects_kb(items),
    )


@router.callback_query(SubjectCallback.filter())
async def subject_selected(call: CallbackQuery, callback_data: SubjectCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(group_subject_id=callback_data.group_subject_id, sort="alpha", page_subject=1)
    await show_subject_view(call.message, session, state)
    await state.set_state(SubjectStates.viewing_subject)


async def show_subject_view(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    edit_message: Message | None = None,
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

    total = await total_active_works(session, group_subject_id)
    subs_map = await submissions_map(session, group_subject_id)
    students = await list_group_students(session, gs.group_id)

    sort_by = data.get("sort", "alpha")
    if sort_by == "count":
        students.sort(key=lambda s: len(subs_map.get(s.id, [])), reverse=True)
    else:
        students.sort(key=lambda s: s.last_name)

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
            full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
            submitted = subs_map.get(student.id, [])
            lines.append(f"{idx}. {full_name} — {len(submitted)}/{total}")
            lines.append(render_work_row(total, submitted))
    else:
        lines.append("В группе пока нет студентов.")
    lines.append("")
    lines.append("Легенда: 🟩 — сдано, цифра — номер несданной работы.")

    page_kb = pagination_kb("subject", page, total_pages)
    text = "\n".join(lines)

    state_data = await state.get_data()
    list_msg_id = state_data.get("subject_list_message_id")
    actions_msg_id = state_data.get("subject_actions_message_id")
    user = await get_user_by_tg(session, message.from_user.id)
    is_starosta = bool(user and user.role == Role.STAROSTA.value)

    if edit_message:
        try:
            await edit_message.edit_text(text, reply_markup=page_kb)
            await state.update_data(subject_list_message_id=edit_message.message_id)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                pass
            else:
                list_msg = await message.answer(text, reply_markup=page_kb)
                await state.update_data(subject_list_message_id=list_msg.message_id)
        except Exception:
            list_msg = await message.answer(text, reply_markup=page_kb)
            await state.update_data(subject_list_message_id=list_msg.message_id)
    elif list_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=list_msg_id,
                text=text,
                reply_markup=page_kb,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                pass
            else:
                list_msg = await message.answer(text, reply_markup=page_kb)
                await state.update_data(subject_list_message_id=list_msg.message_id)
        except Exception:
            list_msg = await message.answer(text, reply_markup=page_kb)
            await state.update_data(subject_list_message_id=list_msg.message_id)
    else:
        list_msg = await message.answer(text, reply_markup=page_kb)
        await state.update_data(subject_list_message_id=list_msg.message_id)

    actions_text = "Быстрые действия по дисциплине:"
    actions_kb = subject_inline_actions_kb(is_starosta=is_starosta)
    if actions_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=actions_msg_id,
                text=actions_text,
                reply_markup=actions_kb,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                pass
            else:
                actions_msg = await message.answer(actions_text, reply_markup=actions_kb)
                await state.update_data(subject_actions_message_id=actions_msg.message_id)
        except Exception:
            actions_msg = await message.answer(actions_text, reply_markup=actions_kb)
            await state.update_data(subject_actions_message_id=actions_msg.message_id)
    else:
        actions_msg = await message.answer(actions_text, reply_markup=actions_kb)
        await state.update_data(subject_actions_message_id=actions_msg.message_id)
        await message.answer("Навигация:", reply_markup=subject_actions_kb())


@router.callback_query(ActionCallback.filter(F.name == "sort"))
async def sort_action(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer("Выберите способ сортировки списка:", reply_markup=sort_kb())


@router.callback_query(SortCallback.filter())
async def apply_sort(call: CallbackQuery, callback_data: SortCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(sort=callback_data.by)
    await show_subject_view(call.message, session, state)


@router.callback_query(PageCallback.filter(F.action == "subject"))
async def subject_page(call: CallbackQuery, callback_data: PageCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(page_subject=callback_data.page)
    await show_subject_view(call.message, session, state, edit_message=call.message)


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

    if user.role == Role.STAROSTA.value:
        await state.update_data(mark_for_student=None, page_mark=1)
        await show_student_selection(call.message, session, state)
    else:
        await state.update_data(mark_for_student=user.student_id)
        numbers = await list_active_work_numbers(session, group_subject_id)
        await call.message.answer("Выберите номер работы для отметки:", reply_markup=works_kb(numbers))
        await state.set_state(SubjectStates.marking_work)


@router.callback_query(StudentCallback.filter())
async def mark_select_student(call: CallbackQuery, callback_data: StudentCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    group_subject_id = data.get("group_subject_id")
    if not group_subject_id:
        await call.message.answer("Сначала выберите дисциплину.")
        return
    await state.update_data(mark_for_student=callback_data.student_id)
    numbers = await list_active_work_numbers(session, group_subject_id)
    await call.message.answer("Выберите номер работы для отметки:", reply_markup=works_kb(numbers))
    await state.set_state(SubjectStates.marking_work)


@router.callback_query(PageCallback.filter(F.action == "mark"))
async def mark_page(call: CallbackQuery, callback_data: PageCallback, session: AsyncSession, state: FSMContext):
    await call.answer()
    await state.update_data(page_mark=callback_data.page)
    await show_student_selection(call.message, session, state)


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

    await state.update_data(work_number=callback_data.number)
    await call.message.answer(
        "Введите балл от 0 до 100.\n"
        "Если оценка не нужна, нажмите «Без балла».",
        reply_markup=score_optional_kb(),
    )
    await state.set_state(SubjectStates.entering_score)


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
    else:
        await message.answer("Сдача зафиксирована.")

    await show_subject_view(message, session, state)
    await state.set_state(SubjectStates.viewing_subject)


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

    details = await get_submission_details(session, user.student_id, group_subject_id)
    total = await total_active_works(session, group_subject_id)
    by_number = {d.work_number: d for d in details}
    lines = ["Ваша статистика:"]
    scores: list[int] = []
    for i in range(1, total + 1):
        if i in by_number:
            if by_number[i].score is None:
                lines.append(f"{i}. Сдано🟩 – без балла")
            else:
                scores.append(by_number[i].score)
                lines.append(f"{i}. Сдано🟩 – Балл {by_number[i].score}")
        else:
            lines.append(f"{i}. Не сдано🟥")
    avg_score = (sum(scores) / len(scores)) if scores else 0
    grade = score_to_grade(avg_score)
    lines.append("")
    lines.append(f"Средний балл: {int(avg_score)}")
    lines.append(f"Оценка: {grade}")
    await call.message.answer("\n".join(lines))


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

    lines = ["📊 Очередность сдач (по убыванию приоритета):", ""]
    for idx, item in enumerate(items, start=1):
        percent = int(item["priority"] * 100)
        lines.append(f"{idx}. {item['full_name']}")
        lines.append(
            f"приоритет {percent}% | сдано {item['completed']}/{item['total']} | средний балл {int(item['avg_score'])}"
        )
        lines.append("")
    await message.answer("\n".join(lines).strip())


@router.message(F.text.in_(BACK_ALIASES))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню. Выберите раздел:", reply_markup=main_menu_kb())


@router.callback_query(ActionCallback.filter(F.name == "noop"))
async def noop_callback(call: CallbackQuery):
    await call.answer()


@router.callback_query(ActionCallback.filter(F.name == "work_back"))
async def work_back(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await show_subject_view(call.message, session, state)


@router.callback_query(ActionCallback.filter(F.name == "mark_back"))
async def mark_back(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
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
    else:
        await call.message.answer("Сдача зафиксирована без балла.")
    await show_subject_view(call.message, session, state)
    await state.set_state(SubjectStates.viewing_subject)


@router.callback_query(ActionCallback.filter(F.name == "cancel_score"))
async def cancel_score_submit(call: CallbackQuery, session: AsyncSession, state: FSMContext):
    await call.answer()
    await call.message.answer("Отметка отменена.")
    await show_subject_view(call.message, session, state)
    await state.set_state(SubjectStates.viewing_subject)


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
