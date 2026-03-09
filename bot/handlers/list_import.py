from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Role
from bot.services.import_list import parse_text_list, parse_excel
from bot.services.roster import get_or_create_faculty, get_or_create_group, add_students_to_group
from bot.services.users import get_user_by_tg
from bot.states.list_import import ListImportStates

router = Router()


@router.message(Command("list"))
async def list_start(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await message.answer("Команда доступна только старосте.")
        return

    await state.clear()
    await message.answer("Введите факультет:")
    await state.set_state(ListImportStates.waiting_faculty)


@router.message(ListImportStates.waiting_faculty)
async def list_faculty(message: Message, state: FSMContext):
    await state.update_data(faculty=message.text.strip())
    await message.answer("Введите группу:")
    await state.set_state(ListImportStates.waiting_group)


@router.message(ListImportStates.waiting_group)
async def list_group(message: Message, state: FSMContext):
    await state.update_data(group=message.text.strip())
    await message.answer("Отправьте список студентов (текст, .txt или .xlsx).")
    await state.set_state(ListImportStates.waiting_list)


@router.message(ListImportStates.waiting_list)
async def list_upload(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or user.role != Role.STAROSTA.value:
        await message.answer("Команда доступна только старосте.")
        await state.clear()
        return

    data = await state.get_data()
    faculty_name = data.get("faculty")
    group_name = data.get("group")

    if not faculty_name or not group_name:
        await message.answer("Не удалось определить факультет/группу.")
        await state.clear()
        return

    faculty = await get_or_create_faculty(session, faculty_name)
    group = await get_or_create_group(session, group_name, faculty.id)
    if group.roster_loaded:
        await message.answer("Список уже загружен. Ничего не изменено.")
        await state.clear()
        return

    students = []
    if message.document:
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        content = file_bytes.read()
        if message.document.file_name and message.document.file_name.lower().endswith(".xlsx"):
            students = parse_excel(content)
        else:
            students = parse_text_list(content.decode("utf-8", errors="ignore"))
    else:
        students = parse_text_list(message.text or "")

    if not students:
        await message.answer("Не удалось распознать список. Проверьте формат.")
        return

    count = await add_students_to_group(session, group.id, students)
    group.roster_loaded = True
    await session.commit()

    await message.answer(f"Загружено студентов: {count}")
    await state.clear()
