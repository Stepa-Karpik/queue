from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Role, SubjectKind
from bot.services.subjects import (
    create_subject_with_works,
    add_work_number,
    deactivate_work_number,
    get_group_subject_by_name,
)
from bot.services.students import get_student_group
from bot.services.users import get_user_by_tg
from bot.states.admin import AdminStates

router = Router()


async def ensure_starosta(message: Message, session: AsyncSession) -> bool:
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await message.answer("Команда доступна только старосте.")
        return False
    return True


@router.message(Command("add_subject"))
async def add_subject_start(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        return
    await state.clear()
    await message.answer("Введите: тип (lab/practice);название;кол-во работ")
    await state.set_state(AdminStates.waiting_add_subject)


@router.message(AdminStates.waiting_add_subject)
async def add_subject_finish(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        await state.clear()
        return
    parts = [p.strip() for p in (message.text or "").split(";")]
    if len(parts) != 3:
        await message.answer("Неверный формат. Пример: lab;Алгоритмы и СД;10")
        return
    kind_str, name, count_str = parts
    try:
        count = int(count_str)
    except ValueError:
        await message.answer("Количество работ должно быть числом.")
        return
    kind = SubjectKind.LAB if kind_str.lower() == "lab" else SubjectKind.PRACTICE

    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_student_group(session, user.student_id)
    await create_subject_with_works(session, group.id, name, kind, count)
    await message.answer("Дисциплина добавлена.")
    await state.clear()


@router.message(Command("remove_subject"))
async def remove_subject_start(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        return
    await state.clear()
    await message.answer("Введите название дисциплины для удаления:")
    await state.set_state(AdminStates.waiting_remove_subject)


@router.message(AdminStates.waiting_remove_subject)
async def remove_subject_finish(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        await state.clear()
        return
    name = (message.text or "").strip()
    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_student_group(session, user.student_id)
    gs = await get_group_subject_by_name(session, group.id, name)
    if not gs:
        await message.answer("Дисциплина не найдена.")
        return
    gs.is_active = False
    await session.commit()
    await message.answer("Дисциплина удалена.")
    await state.clear()


@router.message(Command("add_work"))
async def add_work_start(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        return
    await state.clear()
    await message.answer("Введите название дисциплины для добавления работы:")
    await state.set_state(AdminStates.waiting_add_work)


@router.message(AdminStates.waiting_add_work)
async def add_work_finish(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        await state.clear()
        return
    name = (message.text or "").strip()
    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_student_group(session, user.student_id)
    gs = await get_group_subject_by_name(session, group.id, name)
    if not gs:
        await message.answer("Дисциплина не найдена.")
        return
    new_number = await add_work_number(session, gs.id)
    await message.answer(f"Добавлена работа №{new_number}.")
    await state.clear()


@router.message(Command("remove_work"))
async def remove_work_start(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        return
    await state.clear()
    await message.answer("Введите: название дисциплины;номер")
    await state.set_state(AdminStates.waiting_remove_work)


@router.message(AdminStates.waiting_remove_work)
async def remove_work_finish(message: Message, state: FSMContext, session: AsyncSession):
    if not await ensure_starosta(message, session):
        await state.clear()
        return
    parts = [p.strip() for p in (message.text or "").split(";")]
    if len(parts) != 2:
        await message.answer("Неверный формат. Пример: Алгоритмы и СД;3")
        return
    name, number_str = parts
    try:
        number = int(number_str)
    except ValueError:
        await message.answer("Номер должен быть числом.")
        return
    user = await get_user_by_tg(session, message.from_user.id)
    group = await get_student_group(session, user.student_id)
    gs = await get_group_subject_by_name(session, group.id, name)
    if not gs:
        await message.answer("Дисциплина не найдена.")
        return
    ok = await deactivate_work_number(session, gs.id, number)
    if not ok:
        await message.answer("Работа не найдена или уже удалена.")
        return
    await message.answer("Работа удалена (номер сохранён).")
    await state.clear()
