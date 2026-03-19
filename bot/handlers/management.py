from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import (
    ConfirmCallback,
    ManageMenuCallback,
    ManagePageCallback,
    ManageRemoveWorkCallback,
    ManageRoleCallback,
    ManageSubmissionActionCallback,
    ManageSubmissionSubjectCallback,
    ManageSubmissionWorkCallback,
    ManageStudentCallback,
    ManageSubjectCallback,
    ManageTeacherCallback,
    ManageTeacherDisciplineCallback,
    ManageTeacherLessonTypeCallback,
)
from bot.keyboards.common import STAROSTA_ALIASES, main_menu_kb
from bot.keyboards.management import (
    management_main_kb,
    management_remove_works_kb,
    management_role_kb,
    management_score_kb,
    management_submission_actions_kb,
    management_students_kb,
    management_subject_card_kb,
    management_subject_kind_kb,
    management_subjects_kb,
    management_subjects_menu_kb,
    management_submission_subjects_kb,
    management_submission_works_kb,
    management_teacher_disciplines_kb,
    management_teacher_lesson_types_kb,
    management_teachers_kb,
    management_teachers_menu_kb,
    management_user_card_kb,
    management_users_menu_kb,
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
    toggle_student_inactive,
    update_student_full_name,
)
from bot.services.subjects import add_work_number, create_subject_with_works, deactivate_work_number, list_active_work_numbers
from bot.services.subjects import deactivate_last_work_number
from bot.services.submissions import delete_submission, list_submitted_numbers, submit_work
from bot.services.teachers import (
    add_group_teacher,
    delete_group_teacher,
    get_group_teacher,
    list_group_teachers_for_slot,
    list_teacher_disciplines,
    list_teacher_lesson_types,
    rename_group_teacher,
    replace_group_teachers_from_schedule,
)
from bot.services.users import get_effective_group, get_user_by_tg, is_admin_mode, is_admin_user
from bot.states.management import ManagementStates
from bot.utils.admin_state import cancel_admin_broadcast_flow
from bot.utils.names import format_full_name, format_short_name, normalize_group_name, split_full_name
from bot.utils.submission_flow import (
    get_submission_mode_from_action,
    get_submission_subject_prompt,
    get_submission_work_prompt,
)
from bot.utils.teacher_names import teacher_lesson_type_label

router = Router()
PAGE_SIZE = 8


async def _get_actor_and_group(session: AsyncSession, tg_id: int):
    user = await get_user_by_tg(session, tg_id)
    if not user or (user.role != Role.STAROSTA.value and not is_admin_mode(user)):
        return None, None
    group = await get_effective_group(session, user)
    return user, group


@router.message(F.text.in_(STAROSTA_ALIASES))
async def open_management_panel(message: Message, state: FSMContext, session: AsyncSession):
    await cancel_admin_broadcast_flow(message, state)
    user, group = await _get_actor_and_group(session, message.from_user.id)
    if not user:
        await message.answer("Раздел доступен только старосте или админу.")
        return
    if not group:
        await message.answer("Сначала выберите группу.")
        return

    await state.update_data(mg_group_id=group.id, mg_users_page=1, mg_subjects_page=1)
    await state.set_state(ManagementStates.viewing_panel)
    await message.answer(
        f"Режим управления группой {normalize_group_name(group.name)} включен.\nВыберите раздел:",
        reply_markup=management_main_kb(),
    )


@router.callback_query(ManageMenuCallback.filter(F.section == "main"))
async def management_main_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    user, group = await _get_actor_and_group(session, call.from_user.id)
    if not user or not group:
        await call.message.answer("Сначала выберите группу.")
        return

    if callback_data.action == "users":
        await call.message.edit_text("Управление пользователями:", reply_markup=management_users_menu_kb())
        return
    if callback_data.action == "subjects":
        await call.message.edit_text("Управление дисциплинами:", reply_markup=management_subjects_menu_kb())
        return
    if callback_data.action == "teachers":
        await call.message.edit_text("Управление преподавателями:", reply_markup=management_teachers_menu_kb())
        return
    if callback_data.action == "exit":
        await state.set_state(ManagementStates.viewing_panel)
        await call.message.edit_text("Режим управления выключен.")
        await call.message.answer(
            "Главное меню.",
            reply_markup=main_menu_kb(
                is_starosta=user.role == Role.STAROSTA.value,
                is_admin=is_admin_user(user),
                admin_mode=is_admin_mode(user),
            ),
        )


@router.callback_query(ManageMenuCallback.filter(F.section == "users"))
async def users_menu_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    _, group = await _get_actor_and_group(session, call.from_user.id)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    if callback_data.action == "add":
        await state.set_state(ManagementStates.waiting_add_user_full_name)
        await call.message.answer("Введите ФИО нового пользователя в формате: Фамилия Имя Отчество")
        return
    if callback_data.action == "list":
        await show_users_list(call.message, session, state, group.id, page=1, edit=True)
        return
    if callback_data.action == "back":
        await call.message.edit_text("Выберите раздел:", reply_markup=management_main_kb())


@router.callback_query(ManageMenuCallback.filter(F.section == "teachers"))
async def teachers_menu_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    _, group = await _get_actor_and_group(session, call.from_user.id)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    if callback_data.action in {"add", "edit", "delete"}:
        await state.set_state(ManagementStates.viewing_panel)
        await show_teacher_disciplines(call.message, session, state, group.id, callback_data.action, edit=True)
        return
    if callback_data.action == "parse":
        await call.message.answer(
            "Вы уверены? Все ручные изменения будут удалены.",
            reply_markup=_confirm("mg_parse_teachers", str(group.id)),
        )
        return
    if callback_data.action == "back":
        await call.message.edit_text("Выберите раздел:", reply_markup=management_main_kb())


@router.callback_query(ManageMenuCallback.filter(F.section == "teacher_types"))
async def teacher_types_back(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    action = data.get("mg_teacher_action")
    discipline = data.get("mg_selected_teacher_discipline")
    if not group_id or action not in {"add", "edit", "delete"} or not discipline:
        await show_teachers_menu(call.message, edit=True)
        return
    await show_teacher_lesson_types(call.message, session, state, int(group_id), str(action), str(discipline), edit=True)


@router.callback_query(ManagePageCallback.filter(F.section == "users"))
async def users_page(call: CallbackQuery, callback_data: ManagePageCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    if not group_id:
        await call.message.answer("Сначала выберите группу.")
        return
    await show_users_list(call.message, session, state, int(group_id), page=callback_data.page, edit=True)


@router.message(ManagementStates.waiting_add_user_full_name)
async def add_user_message(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    if not group_id:
        await message.answer("Сначала выберите группу.")
        await state.clear()
        return

    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Неверный формат. Пример: Иванов Иван Иванович")
        return

    student = await add_student_to_group(session, int(group_id), last, first, middle)
    await state.set_state(ManagementStates.viewing_panel)
    await message.answer(f"Пользователь добавлен: {format_full_name(student.last_name, student.first_name, student.middle_name)}")
    await show_user_card(message, session, student.id, edit=False)


@router.callback_query(ManageStudentCallback.filter())
async def user_actions(call: CallbackQuery, callback_data: ManageStudentCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    actor, _ = await _get_actor_and_group(session, call.from_user.id)
    if not actor:
        await call.message.answer("Недостаточно прав.")
        return

    student = await get_student_with_user(session, callback_data.student_id)
    if not student:
        await call.message.answer("Пользователь не найден.")
        return

    if callback_data.action == "view":
        await state.update_data(mg_selected_student_id=student.id)
        await show_user_card(call.message, session, student.id, edit=True)
        return
    if callback_data.action == "rename":
        await state.update_data(mg_selected_student_id=student.id)
        await state.set_state(ManagementStates.waiting_edit_user_full_name)
        await call.message.answer("Введите новое ФИО пользователя:")
        return
    if callback_data.action == "role":
        await call.message.edit_text("Выберите роль пользователя:", reply_markup=management_role_kb(student.id, student.user.role if student.user else None))
        return
    if callback_data.action == "inactive":
        ok, text = await toggle_student_inactive(session, student.id)
        await call.message.answer(text)
        if ok:
            await show_user_card(call.message, session, student.id, edit=False)
        return
    if callback_data.action == "delete":
        if actor.student_id == student.id:
            await call.message.answer("Нельзя удалить самого себя из режима управления.")
            return
        await call.message.answer(
            f"Удалить пользователя {format_full_name(student.last_name, student.first_name, student.middle_name)}?",
            reply_markup=InlineDeleteConfirm.user(student.id),
        )
        return
    if callback_data.action == "submissions":
        await state.update_data(mg_selected_student_id=student.id, mg_submission_mode=None)
        await show_submission_actions(call.message, session, student.id, edit=True)
        return

    submission_mode = get_submission_mode_from_action(callback_data.action)
    if submission_mode:
        await state.update_data(mg_selected_student_id=student.id, mg_submission_mode=submission_mode)
        await show_submission_subjects(call.message, session, state, student.id, edit=True)
        return

    if callback_data.action == "submission_subjects":
        data = await state.get_data()
        if data.get("mg_submission_mode") not in {"add", "delete"}:
            await show_submission_actions(call.message, session, student.id, edit=True)
            return
        await show_submission_subjects(call.message, session, state, student.id, edit=True)
        return


@router.callback_query(ManageSubmissionActionCallback.filter())
async def submission_action_menu(call: CallbackQuery, callback_data: ManageSubmissionActionCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    student = await get_student_with_user(session, callback_data.student_id)
    if not student:
        await call.message.answer("Пользователь не найден.")
        return

    submission_mode = callback_data.mode if callback_data.mode in {"add", "delete"} else None
    if not submission_mode:
        await call.message.answer("Не удалось определить режим управления сдачей.")
        return

    await state.update_data(mg_selected_student_id=student.id, mg_submission_mode=submission_mode)
    await show_submission_subjects(call.message, session, state, student.id, edit=True)


@router.message(ManagementStates.waiting_edit_user_full_name)
async def rename_user_message(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    student_id = data.get("mg_selected_student_id")
    if not student_id:
        await message.answer("Сначала выберите пользователя.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer("Неверный формат. Пример: Иванов Иван Иванович")
        return

    ok = await update_student_full_name(session, int(student_id), last, first, middle)
    await state.set_state(ManagementStates.viewing_panel)
    if not ok:
        await message.answer("Не удалось обновить ФИО.")
        return
    await message.answer("ФИО обновлено.")
    await show_user_card(message, session, int(student_id), edit=False)


@router.message(ManagementStates.waiting_add_teacher_name)
async def add_teacher_message(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    discipline = data.get("mg_selected_teacher_discipline")
    lesson_type = data.get("mg_selected_teacher_lesson_type")
    if not group_id or not discipline or not lesson_type:
        await message.answer("Сначала выберите группу.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    ok, text = await add_group_teacher(session, int(group_id), str(discipline), str(lesson_type), message.text or "")
    await message.answer(text)
    if not ok:
        return

    await state.set_state(ManagementStates.viewing_panel)
    await show_teachers_list(message, session, state, int(group_id), "edit", str(discipline), str(lesson_type), edit=False)


@router.message(ManagementStates.waiting_edit_teacher_name)
async def edit_teacher_message(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    teacher_id = data.get("mg_selected_teacher_id")
    group_id = data.get("mg_group_id")
    discipline = data.get("mg_selected_teacher_discipline")
    lesson_type = data.get("mg_selected_teacher_lesson_type")
    if not teacher_id or not group_id or not discipline or not lesson_type:
        await message.answer("Сначала выберите преподавателя.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    ok, text = await rename_group_teacher(session, int(teacher_id), message.text or "")
    await message.answer(text)
    if not ok:
        return

    await state.set_state(ManagementStates.viewing_panel)
    await show_teachers_list(message, session, state, int(group_id), "edit", str(discipline), str(lesson_type), edit=False)


@router.callback_query(ManageRoleCallback.filter())
async def set_user_role(call: CallbackQuery, callback_data: ManageRoleCallback, session: AsyncSession):
    await call.answer()
    role = Role.STAROSTA if callback_data.role == Role.STAROSTA.value else Role.STUDENT
    ok, msg = await set_role_for_student_user(session, callback_data.student_id, role)
    await call.message.answer(msg)
    if ok:
        await show_user_card(call.message, session, callback_data.student_id, edit=False)


@router.callback_query(ManageTeacherCallback.filter())
async def teacher_actions(call: CallbackQuery, callback_data: ManageTeacherCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    _, group = await _get_actor_and_group(session, call.from_user.id)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    teacher = await get_group_teacher(session, callback_data.teacher_id)
    if not teacher or teacher.group_id != group.id:
        await call.message.answer("Преподаватель не найден.")
        return

    if callback_data.action == "edit":
        await state.update_data(
            mg_selected_teacher_id=teacher.id,
            mg_selected_teacher_discipline=teacher.discipline,
            mg_selected_teacher_lesson_type=teacher.lesson_type,
        )
        await state.set_state(ManagementStates.waiting_edit_teacher_name)
        await call.message.answer(
            f"Дисциплина: {teacher.discipline}\n"
            f"Вид пары: {teacher_lesson_type_label(teacher.lesson_type)}\n"
            f"Введите новое ФИО для преподавателя {teacher.full_name}."
        )
        return

    if callback_data.action == "delete":
        ok, text = await delete_group_teacher(session, teacher.id)
        await call.message.answer(text)
        if ok:
            await show_teachers_list(
                call.message,
                session,
                state,
                group.id,
                "delete",
                teacher.discipline,
                teacher.lesson_type,
                edit=True,
            )


@router.callback_query(ManageTeacherDisciplineCallback.filter())
async def teacher_discipline_selected(
    call: CallbackQuery,
    callback_data: ManageTeacherDisciplineCallback,
    state: FSMContext,
    session: AsyncSession,
):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    disciplines = data.get("mg_teacher_disciplines") or []
    if not group_id or callback_data.option_index < 0 or callback_data.option_index >= len(disciplines):
        await show_teachers_menu(call.message, edit=True)
        return

    discipline = disciplines[callback_data.option_index]
    await show_teacher_lesson_types(
        call.message,
        session,
        state,
        int(group_id),
        callback_data.action,
        str(discipline),
        edit=True,
    )


@router.callback_query(ManageTeacherLessonTypeCallback.filter())
async def teacher_lesson_type_selected(
    call: CallbackQuery,
    callback_data: ManageTeacherLessonTypeCallback,
    state: FSMContext,
    session: AsyncSession,
):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    discipline = data.get("mg_selected_teacher_discipline")
    lesson_types = data.get("mg_teacher_lesson_types") or []
    if not group_id or not discipline or callback_data.option_index < 0 or callback_data.option_index >= len(lesson_types):
        await show_teachers_menu(call.message, edit=True)
        return

    lesson_type = lesson_types[callback_data.option_index]
    await state.update_data(mg_selected_teacher_lesson_type=lesson_type, mg_teacher_action=callback_data.action)
    if callback_data.action == "add":
        await state.set_state(ManagementStates.waiting_add_teacher_name)
        await call.message.answer(
            f"Дисциплина: {discipline}\n"
            f"Вид пары: {teacher_lesson_type_label(str(lesson_type))}\n"
            "Введите ФИО преподавателя."
        )
        return

    await show_teachers_list(
        call.message,
        session,
        state,
        int(group_id),
        callback_data.action,
        str(discipline),
        str(lesson_type),
        edit=True,
    )


@router.callback_query(ConfirmCallback.filter(F.action == "mg_parse_teachers"))
async def parse_teachers_confirm(call: CallbackQuery, callback_data: ConfirmCallback, session: AsyncSession):
    await call.answer()
    _, group = await _get_actor_and_group(session, call.from_user.id)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    if callback_data.value == "no":
        await show_teachers_menu(call.message, edit=True)
        return

    ok, text = await replace_group_teachers_from_schedule(session, group.id)
    if ok:
        await show_teachers_menu(call.message, edit=True, prefix=text)
        return
    await _safe_edit_or_answer(call.message, text, management_teachers_menu_kb(), edit=True)


@router.callback_query(ConfirmCallback.filter(F.action == "mg_delete_user"))
async def delete_user_confirm(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    if callback_data.value == "no":
        student_id = data.get("mg_selected_student_id")
        if student_id:
            await show_user_card(call.message, session, int(student_id), edit=False)
        return

    ok = await delete_student_with_related(session, int(callback_data.value))
    await call.message.answer("Пользователь удален." if ok else "Не удалось удалить пользователя.")
    group_id = data.get("mg_group_id")
    if group_id:
        await show_users_list(call.message, session, state, int(group_id), page=1, edit=False)


@router.callback_query(ManageMenuCallback.filter(F.section == "user_card"))
async def user_card_back(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    page = int(data.get("mg_users_page", 1))
    if group_id:
        await show_users_list(call.message, session, state, int(group_id), page=page, edit=True)


@router.callback_query(ManageMenuCallback.filter(F.section == "subjects"))
async def subjects_menu_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    if not group_id:
        await call.message.answer("Сначала выберите группу.")
        return

    if callback_data.action == "add":
        await call.message.edit_text("Выберите тип дисциплины:", reply_markup=management_subject_kind_kb())
        return
    if callback_data.action == "list":
        await show_subjects_list(call.message, session, state, int(group_id), page=1, edit=True)
        return
    if callback_data.action == "back":
        await call.message.edit_text("Выберите раздел:", reply_markup=management_main_kb())


@router.callback_query(ManageMenuCallback.filter(F.section == "subject_kind"))
async def subject_kind_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext):
    await call.answer()
    if callback_data.action == "back":
        await call.message.edit_text("Управление дисциплинами:", reply_markup=management_subjects_menu_kb())
        return

    await state.update_data(mg_add_subject_kind=callback_data.action)
    await state.set_state(ManagementStates.waiting_add_subject_name)
    await call.message.answer("Введите название дисциплины:")


@router.message(ManagementStates.waiting_add_subject_name)
async def add_subject_name(message: Message, state: FSMContext):
    await state.update_data(mg_add_subject_name=(message.text or "").strip())
    await state.set_state(ManagementStates.waiting_add_subject_count)
    await message.answer("Введите количество работ:")


@router.message(ManagementStates.waiting_add_subject_count)
async def add_subject_count(message: Message, state: FSMContext, session: AsyncSession):
    try:
        count = int(message.text or "")
    except ValueError:
        await message.answer("Введите число.")
        return
    if count <= 0:
        await message.answer("Количество работ должно быть больше 0.")
        return

    data = await state.get_data()
    group_id = data.get("mg_group_id")
    kind_value = data.get("mg_add_subject_kind")
    name = data.get("mg_add_subject_name")
    if not all([group_id, kind_value, name]):
        await message.answer("Не удалось определить параметры дисциплины.")
        await state.clear()
        return

    kind = SubjectKind.LAB if kind_value == "lab" else SubjectKind.PRACTICE
    await create_subject_with_works(session, int(group_id), name, kind, count)
    await state.set_state(ManagementStates.viewing_panel)
    await message.answer("Дисциплина добавлена.")
    await show_subjects_list(message, session, state, int(group_id), page=1, edit=False)


@router.callback_query(ManagePageCallback.filter(F.section == "subjects"))
async def subjects_page(call: CallbackQuery, callback_data: ManagePageCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    if group_id:
        await show_subjects_list(call.message, session, state, int(group_id), page=callback_data.page, edit=True)


@router.callback_query(ManageSubjectCallback.filter())
async def subject_actions(call: CallbackQuery, callback_data: ManageSubjectCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    action = callback_data.action

    if action == "view":
        await state.update_data(mg_selected_subject_id=callback_data.group_subject_id)
        await show_subject_card(call.message, session, callback_data.group_subject_id, edit=True)
        return
    if action == "rename":
        await state.update_data(mg_selected_subject_id=callback_data.group_subject_id)
        await state.set_state(ManagementStates.waiting_rename_subject)
        await call.message.answer("Введите новое название дисциплины:")
        return
    if action == "kind":
        current = await get_group_subject_active(session, callback_data.group_subject_id)
        if not current:
            await call.message.answer("Дисциплина не найдена.")
            return
        new_kind = SubjectKind.PRACTICE if current.subject.kind == SubjectKind.LAB.value else SubjectKind.LAB
        ok, msg = await set_group_subject_kind(session, callback_data.group_subject_id, new_kind)
        await call.message.answer(msg)
        if ok:
            await show_subject_card(call.message, session, callback_data.group_subject_id, edit=False)
        return
    if action == "add_work":
        await add_work_number(session, callback_data.group_subject_id)
        await show_subject_card(call.message, session, callback_data.group_subject_id, edit=True)
        return
    if action == "remove_work":
        ok = await deactivate_last_work_number(session, callback_data.group_subject_id)
        if not ok:
            await call.message.answer("Нет активных работ.")
            return
        await show_subject_card(call.message, session, callback_data.group_subject_id, edit=True)
        return
    if action == "delete":
        await call.message.answer(
            "Удалить дисциплину?",
            reply_markup=InlineDeleteConfirm.subject(callback_data.group_subject_id),
        )
        return


@router.message(ManagementStates.waiting_rename_subject)
async def rename_subject_message(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    group_subject_id = data.get("mg_selected_subject_id")
    if not group_subject_id:
        await message.answer("Сначала выберите дисциплину.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    ok, msg = await rename_group_subject(session, int(group_subject_id), (message.text or "").strip())
    await message.answer(msg)
    await state.set_state(ManagementStates.viewing_panel)
    if ok:
        await show_subject_card(message, session, int(group_subject_id), edit=False)


@router.callback_query(ConfirmCallback.filter(F.action == "mg_delete_subject"))
async def delete_subject_confirm(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    if callback_data.value == "no":
        subject_id = data.get("mg_selected_subject_id")
        if subject_id:
            await show_subject_card(call.message, session, int(subject_id), edit=False)
        return

    ok = await deactivate_group_subject(session, int(callback_data.value))
    await call.message.answer("Дисциплина удалена." if ok else "Не удалось удалить дисциплину.")
    group_id = data.get("mg_group_id")
    if group_id:
        await show_subjects_list(call.message, session, state, int(group_id), page=1, edit=False)


@router.callback_query(ManageMenuCallback.filter(F.section == "subject_card"))
async def subject_card_back(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    group_id = data.get("mg_group_id")
    page = int(data.get("mg_subjects_page", 1))
    if group_id:
        await show_subjects_list(call.message, session, state, int(group_id), page=page, edit=True)


@router.callback_query(ManageSubmissionSubjectCallback.filter())
async def submission_subject_selected(call: CallbackQuery, callback_data: ManageSubmissionSubjectCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if callback_data.mode != "select":
        await call.message.answer("Не удалось определить дисциплину для сдачи.")
        return
    await state.update_data(
        mg_selected_student_id=callback_data.student_id,
        mg_selected_subject_id=callback_data.group_subject_id,
    )
    await show_submission_works(
        call.message,
        session,
        state,
        callback_data.student_id,
        callback_data.group_subject_id,
        edit=True,
    )


@router.callback_query(ManageSubmissionWorkCallback.filter())
async def submission_work_actions(call: CallbackQuery, callback_data: ManageSubmissionWorkCallback, state: FSMContext, session: AsyncSession):
    if callback_data.mode == "delete":
        ok = await delete_submission(session, callback_data.student_id, callback_data.group_subject_id, callback_data.work_number)
        await call.answer("Сдача удалена." if ok else "Сдача не найдена.")
        await show_submission_works(call.message, session, state, callback_data.student_id, callback_data.group_subject_id, edit=True)
        return

    await call.answer()
    if callback_data.mode == "add":
        await state.update_data(
            mg_submission_student_id=callback_data.student_id,
            mg_submission_group_subject_id=callback_data.group_subject_id,
            mg_submission_work_number=callback_data.work_number,
        )
        await state.set_state(ManagementStates.waiting_submission_score)
        await call.message.answer(
            f"Работа №{callback_data.work_number}. Введите балл от 0 до 100 или нажмите «Без балла».",
            reply_markup=management_score_kb(),
        )
        return

    await call.message.answer("Не удалось определить действие с работой.")


@router.callback_query(ManageRemoveWorkCallback.filter())
async def remove_work_action(call: CallbackQuery, callback_data: ManageRemoveWorkCallback, session: AsyncSession):
    await call.answer()
    ok = await deactivate_work_number(session, callback_data.group_subject_id, callback_data.work_number)
    await call.message.answer("Работа удалена." if ok else "Не удалось удалить работу.")
    await show_subject_card(call.message, session, callback_data.group_subject_id, edit=False)


@router.callback_query(ManageMenuCallback.filter(F.section == "submission_score"))
async def submission_score_actions(call: CallbackQuery, callback_data: ManageMenuCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    student_id = data.get("mg_submission_student_id")
    group_subject_id = data.get("mg_submission_group_subject_id")
    work_number = data.get("mg_submission_work_number")
    if not all([student_id, group_subject_id, work_number]):
        await call.message.answer("Не удалось определить сдачу.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    if callback_data.action == "cancel":
        await state.set_state(ManagementStates.viewing_panel)
        await show_submission_works(call.message, session, state, int(student_id), int(group_subject_id), edit=False)
        return

    if callback_data.action == "none":
        await submit_work(session, int(student_id), int(group_subject_id), int(work_number), None)
        await state.set_state(ManagementStates.viewing_panel)
        await show_submission_works(call.message, session, state, int(student_id), int(group_subject_id), edit=False)


@router.message(ManagementStates.waiting_submission_score)
async def submission_score_message(message: Message, state: FSMContext, session: AsyncSession):
    try:
        score = int(message.text or "")
    except ValueError:
        await message.answer("Введите число от 0 до 100.")
        return
    if score < 0 or score > 100:
        await message.answer("Балл должен быть от 0 до 100.")
        return

    data = await state.get_data()
    student_id = data.get("mg_submission_student_id")
    group_subject_id = data.get("mg_submission_group_subject_id")
    work_number = data.get("mg_submission_work_number")
    if not all([student_id, group_subject_id, work_number]):
        await message.answer("Не удалось определить сдачу.")
        await state.set_state(ManagementStates.viewing_panel)
        return

    await submit_work(session, int(student_id), int(group_subject_id), int(work_number), score)
    await state.set_state(ManagementStates.viewing_panel)
    await show_submission_works(message, session, state, int(student_id), int(group_subject_id), edit=False)


@router.callback_query(ManageMenuCallback.filter((F.section == "noop") & (F.action == "noop")))
async def noop(call: CallbackQuery):
    await call.answer()


async def show_teachers_menu(message: Message, edit: bool, prefix: str | None = None):
    text = "Управление преподавателями:"
    if prefix:
        text = f"{prefix}\n\n{text}"
    await _safe_edit_or_answer(message, text, management_teachers_menu_kb(), edit)


async def show_teacher_disciplines(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    group_id: int,
    action: str,
    edit: bool,
    prefix: str | None = None,
):
    disciplines = await list_teacher_disciplines(session, group_id)
    await state.update_data(
        mg_teacher_action=action,
        mg_teacher_disciplines=disciplines,
        mg_selected_teacher_discipline=None,
        mg_selected_teacher_lesson_type=None,
        mg_selected_teacher_id=None,
    )
    action_title = {
        "add": "добавления преподавателя",
        "edit": "изменения преподавателя",
        "delete": "удаления преподавателя",
    }.get(action, "работы с преподавателями")
    text = f"Выберите дисциплину для {action_title}."
    if not disciplines:
        text = "В расписании пока нет дисциплин с видами пар."
    if prefix:
        text = f"{prefix}\n\n{text}"
    await _safe_edit_or_answer(message, text, management_teacher_disciplines_kb(disciplines, action), edit)


async def show_teacher_lesson_types(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    group_id: int,
    action: str,
    discipline: str,
    edit: bool,
    prefix: str | None = None,
):
    lesson_types = await list_teacher_lesson_types(session, group_id, discipline)
    await state.update_data(
        mg_teacher_action=action,
        mg_selected_teacher_discipline=discipline,
        mg_teacher_lesson_types=lesson_types,
        mg_selected_teacher_lesson_type=None,
        mg_selected_teacher_id=None,
    )
    action_title = {
        "add": "добавления преподавателя",
        "edit": "изменения преподавателя",
        "delete": "удаления преподавателя",
    }.get(action, "работы с преподавателями")
    text = f"Дисциплина: {discipline}\nВыберите вид пары для {action_title}."
    if not lesson_types:
        text = f"Для дисциплины {discipline} пока не найдено видов пары в расписании."
    if prefix:
        text = f"{prefix}\n\n{text}"
    await _safe_edit_or_answer(message, text, management_teacher_lesson_types_kb(lesson_types, action), edit)


async def show_teachers_list(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    group_id: int,
    action: str,
    discipline: str,
    lesson_type: str,
    edit: bool,
    prefix: str | None = None,
):
    teachers = await list_group_teachers_for_slot(session, group_id, discipline, lesson_type)
    await state.update_data(
        mg_teacher_action=action,
        mg_selected_teacher_discipline=discipline,
        mg_selected_teacher_lesson_type=lesson_type,
    )

    action_title = "изменения" if action == "edit" else "удаления"
    items = [(teacher.id, teacher.full_name) for teacher in teachers]
    text = (
        f"Дисциплина: {discipline}\n"
        f"Вид пары: {teacher_lesson_type_label(lesson_type)}\n"
        f"Выберите преподавателя для {action_title}."
    )
    if not teachers:
        text = (
            f"Дисциплина: {discipline}\n"
            f"Вид пары: {teacher_lesson_type_label(lesson_type)}\n"
            "Для этого вида пары преподаватели пока не добавлены."
        )
    if prefix:
        text = f"{prefix}\n\n{text}"
    await _safe_edit_or_answer(message, text, management_teachers_kb(items, action), edit)


async def show_users_list(message: Message, session: AsyncSession, state: FSMContext, group_id: int, page: int, edit: bool):
    students = await list_group_students_with_user(session, group_id)
    total_pages = max(1, (len(students) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    await state.update_data(mg_users_page=page)
    items = []
    for student in students[start:end]:
        label = format_short_name(student.last_name, student.first_name, student.middle_name)
        if student.is_inactive:
            label = f"{label} [неактивен]"
        items.append((student.id, label))
    text = f"Пользователи группы\nСтраница {page}/{total_pages}"
    kb = management_students_kb(items, page, total_pages)
    await _safe_edit_or_answer(message, text, kb, edit)


async def show_user_card(message: Message, session: AsyncSession, student_id: int, edit: bool):
    student = await get_student_with_user(session, student_id)
    if not student:
        await message.answer("Пользователь не найден.")
        return

    tg_status = f"@{student.user.username}" if student.user and student.user.username else "не привязан"
    role = student.user.role if student.user else "не зарегистрирован"
    text = (
        f"Пользователь: {format_full_name(student.last_name, student.first_name, student.middle_name)}\n"
        f"Telegram: {tg_status}\n"
        f"Роль: {role}\n"
        f"Активность: {'неактивен' if student.is_inactive else 'активен'}"
    )
    await _safe_edit_or_answer(message, text, management_user_card_kb(student_id, student.is_inactive), edit)


async def show_submission_actions(message: Message, session: AsyncSession, student_id: int, edit: bool):
    student = await get_student_with_user(session, student_id)
    if not student:
        await message.answer("Пользователь не найден.")
        return

    text = (
        f"Сдачи студента {format_full_name(student.last_name, student.first_name, student.middle_name)}.\n"
        "Выберите действие:"
    )
    await _safe_edit_or_answer(message, text, management_submission_actions_kb(student_id), edit)


async def show_subjects_list(message: Message, session: AsyncSession, state: FSMContext, group_id: int, page: int, edit: bool):
    subjects = await list_group_subjects_all(session, group_id)
    total_pages = max(1, (len(subjects) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    await state.update_data(mg_subjects_page=page)
    items = [
        (item.id, f"{item.subject.name} ({'ЛБ' if item.subject.kind == SubjectKind.LAB.value else 'ПР'})")
        for item in subjects[start:end]
    ]
    text = f"Дисциплины группы\nСтраница {page}/{total_pages}"
    await _safe_edit_or_answer(message, text, management_subjects_kb(items, page, total_pages), edit)


async def show_subject_card(message: Message, session: AsyncSession, group_subject_id: int, edit: bool):
    group_subject = await get_group_subject_active(session, group_subject_id)
    if not group_subject:
        await message.answer("Дисциплина не найдена.")
        return

    numbers = await list_active_work_numbers(session, group_subject_id)
    text = (
        f"Дисциплина: {group_subject.subject.name}\n"
        f"Тип: {'Лабораторные' if group_subject.subject.kind == SubjectKind.LAB.value else 'Практические'}\n"
        f"Количество работ: {len(numbers)}\n"
        f"Активные работы: {', '.join(map(str, numbers)) if numbers else 'нет'}"
    )
    await _safe_edit_or_answer(message, text, management_subject_card_kb(group_subject_id), edit)


async def show_submission_subjects(message: Message, session: AsyncSession, state: FSMContext, student_id: int, edit: bool):
    student = await get_student_with_user(session, student_id)
    if not student:
        await message.answer("Пользователь не найден.")
        return
    data = await state.get_data()
    mode = data.get("mg_submission_mode")
    if mode not in {"add", "delete"}:
        await show_submission_actions(message, session, student_id, edit)
        return
    subjects = await list_group_subjects_all(session, student.group_id)
    items = [(item.id, item.subject.name) for item in subjects]
    text = get_submission_subject_prompt(mode)
    await _safe_edit_or_answer(message, text, management_submission_subjects_kb(items, student_id), edit)


async def show_submission_works(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    student_id: int,
    group_subject_id: int,
    edit: bool,
):
    numbers = await list_active_work_numbers(session, group_subject_id)
    submitted_numbers = await list_submitted_numbers(session, student_id, group_subject_id)
    data = await state.get_data()
    mode = data.get("mg_submission_mode")
    if mode not in {"add", "delete"}:
        await show_submission_actions(message, session, student_id, edit)
        return
    text = get_submission_work_prompt(mode)
    await state.update_data(mg_selected_student_id=student_id, mg_selected_subject_id=group_subject_id)
    await _safe_edit_or_answer(
        message,
        text,
        management_submission_works_kb(group_subject_id, student_id, numbers, submitted_numbers, mode),
        edit,
    )


async def _safe_edit_or_answer(message: Message, text: str, reply_markup, edit: bool):
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup)


class InlineDeleteConfirm:
    @staticmethod
    def user(student_id: int):
        return _confirm("mg_delete_user", str(student_id))

    @staticmethod
    def subject(group_subject_id: int):
        return _confirm("mg_delete_subject", str(group_subject_id))


def _confirm(action: str, value: str):
    from bot.keyboards.common import confirm_kb

    return confirm_kb(action, value)
