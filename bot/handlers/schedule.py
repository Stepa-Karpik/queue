from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import ScheduleCallback
from bot.keyboards.common import SCHEDULE_ALIASES
from bot.keyboards.schedule import (
    schedule_bind_internal_kb,
    schedule_bind_subjects_kb,
    schedule_overview_kb,
)
from bot.models import Role, ScheduleWeekType
from bot.services.schedule import (
    format_schedule_text,
    has_full_schedule,
    lesson_type_label,
    list_bindable_subjects,
    parse_schedule_excel,
    render_week_entries,
    subject_kind_from_schedule_lesson,
    upsert_schedule_binding,
    upsert_schedule_template,
)
from bot.services.subjects import list_group_subjects
from bot.services.users import get_effective_group, get_user_by_tg, is_admin_mode
from bot.states.schedule import ScheduleStates

router = Router()


@router.message(F.text.in_(SCHEDULE_ALIASES))
async def schedule_handler(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        return

    can_manage = user.role == Role.STAROSTA.value or is_admin_mode(user)
    has_schedule = await has_full_schedule(session, group.id)
    if not has_schedule:
        if can_manage:
            await message.answer(
                "Расписание пока не подтягивается автоматически, вы можете добавить его самостоятельно.",
                reply_markup=schedule_overview_kb(can_manage=True, has_schedule=False),
            )
        else:
            await message.answer("Расписание пока не получено.")
        return

    _, entries = await render_week_entries(session, group.id)
    await message.answer(
        format_schedule_text(entries),
        reply_markup=schedule_overview_kb(can_manage=can_manage, has_schedule=True),
    )


@router.callback_query(ScheduleCallback.filter())
async def schedule_callbacks(call: CallbackQuery, callback_data: ScheduleCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    user = await get_user_by_tg(session, call.from_user.id)
    if not user:
        await call.message.answer("Сначала зарегистрируйтесь через /start.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await call.message.answer("Сначала выберите группу.")
        return

    can_manage = user.role == Role.STAROSTA.value or is_admin_mode(user)

    if callback_data.action == "back":
        try:
            await call.message.delete()
        except Exception:
            pass
        return

    if callback_data.action == "back_to_schedule":
        has_schedule = await has_full_schedule(session, group.id)
        _, entries = await render_week_entries(session, group.id)
        await call.message.edit_text(
            format_schedule_text(entries) if has_schedule else "Расписание пока не подтягивается автоматически, вы можете добавить его самостоятельно.",
            reply_markup=schedule_overview_kb(can_manage=can_manage, has_schedule=has_schedule),
        )
        return

    if callback_data.action == "upload":
        if not can_manage:
            await call.message.answer("Загрузка доступна только старосте или админу.")
            return
        await state.update_data(schedule_group_id=group.id)
        await state.set_state(ScheduleStates.waiting_lower_week_file)
        await call.message.answer("Отправьте файл нижней недели (.xlsx).")
        return

    if callback_data.action == "bind":
        if not can_manage:
            await call.message.answer("Привязка доступна только старосте или админу.")
            return
        bindable = await list_bindable_subjects(session, group.id)
        if not bindable:
            await call.message.answer("В расписании нет лабораторных или практических для привязки.")
            return
        await state.update_data(schedule_bind_items=bindable, schedule_bind_external=None, schedule_bind_internal_items=None)
        text = _render_external_bind_list(bindable, None)
        await call.message.edit_text(text, reply_markup=schedule_bind_subjects_kb([(item["discipline_key"], item["discipline_label"]) for item in bindable]))
        return

    if callback_data.action == "pick_external":
        bindable = (await state.get_data()).get("schedule_bind_items") or []
        index = int(callback_data.value) - 1
        if index < 0 or index >= len(bindable):
            await call.message.answer("Не удалось определить элемент расписания.")
            return
        selected = bindable[index]
        await state.update_data(schedule_bind_external=selected)
        text = _render_external_bind_list(bindable, selected["discipline_key"])
        await call.message.edit_text(
            text,
            reply_markup=schedule_bind_subjects_kb(
                [(item["discipline_key"], item["discipline_label"]) for item in bindable],
                selected_key=selected["discipline_key"],
            ),
        )

        subject_kind = subject_kind_from_schedule_lesson(selected["lesson_type"])
        if not subject_kind:
            await call.message.answer("Для этого типа занятия привязка не поддерживается.")
            return
        group_subjects = await list_group_subjects(session, group.id, subject_kind)
        internal_items = [(item.id, item.subject.name) for item in group_subjects]
        await state.update_data(schedule_bind_internal_items=internal_items)
        await call.message.answer(
            _render_internal_bind_list(internal_items, selected["discipline_label"]),
            reply_markup=schedule_bind_internal_kb(internal_items),
        )
        return

    if callback_data.action == "pick_internal":
        data = await state.get_data()
        selected_external = data.get("schedule_bind_external")
        internal_items = data.get("schedule_bind_internal_items") or []
        index = int(callback_data.value) - 1
        if not selected_external or index < 0 or index >= len(internal_items):
            await call.message.answer("Не удалось определить дисциплину.")
            return
        subject_id, subject_name = internal_items[index]
        await upsert_schedule_binding(
            session,
            group_id=group.id,
            discipline_key=selected_external["discipline_key"],
            discipline_label=selected_external["discipline_label"],
            lesson_type=selected_external["lesson_type"],
            group_subject_id=subject_id,
        )
        await call.message.answer(f"Привязка сохранена: {selected_external['discipline_label']} → {subject_name}")
        return


@router.message(ScheduleStates.waiting_lower_week_file)
async def upload_lower_week(message: Message, state: FSMContext, session: AsyncSession):
    if not message.document or not message.document.file_name or not message.document.file_name.lower().endswith(".xlsx"):
        await message.answer("Отправьте файл .xlsx нижней недели.")
        return

    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        await state.clear()
        return

    file = await message.bot.get_file(message.document.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    try:
        source_group_name, week_start, entries = parse_schedule_excel(file_bytes.read())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    if source_group_name and source_group_name != group.name:
        await message.answer(f"Файл относится к группе {source_group_name}, а выбрана группа {group.name}.")
        return

    await upsert_schedule_template(
        session,
        group_id=group.id,
        week_type=ScheduleWeekType.LOWER,
        week_start=week_start,
        entries=entries,
        uploaded_by_user_id=user.id if user else None,
    )
    await state.set_state(ScheduleStates.waiting_upper_week_file)
    await message.answer("Нижняя неделя загружена. Теперь отправьте файл верхней недели (.xlsx).")


@router.message(ScheduleStates.waiting_upper_week_file)
async def upload_upper_week(message: Message, state: FSMContext, session: AsyncSession):
    if not message.document or not message.document.file_name or not message.document.file_name.lower().endswith(".xlsx"):
        await message.answer("Отправьте файл .xlsx верхней недели.")
        return

    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        await state.clear()
        return

    file = await message.bot.get_file(message.document.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    try:
        source_group_name, week_start, entries = parse_schedule_excel(file_bytes.read())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    if source_group_name and source_group_name != group.name:
        await message.answer(f"Файл относится к группе {source_group_name}, а выбрана группа {group.name}.")
        return

    await upsert_schedule_template(
        session,
        group_id=group.id,
        week_type=ScheduleWeekType.UPPER,
        week_start=week_start,
        entries=entries,
        uploaded_by_user_id=user.id if user else None,
    )
    await state.clear()
    _, rendered = await render_week_entries(session, group.id)
    await message.answer(
        "Расписание обновлено.\n\n" + format_schedule_text(rendered),
        reply_markup=schedule_overview_kb(can_manage=True, has_schedule=True),
    )


def _render_external_bind_list(items: list[dict[str, str]], selected_key: str | None) -> str:
    lines = ["Выберите предмет из расписания для привязки:", ""]
    for idx, item in enumerate(items, start=1):
        marker = "🟩 " if item["discipline_key"] == selected_key else ""
        lines.append(f"{marker}{idx}. {item['discipline_label']}")
    return "\n".join(lines)


def _render_internal_bind_list(items: list[tuple[int, str]], source_label: str) -> str:
    lines = [f"Привязка для: {source_label}", "", "Выберите нашу дисциплину:"]
    for idx, (_, name) in enumerate(items, start=1):
        lines.append(f"{idx}. {name}")
    return "\n".join(lines)
