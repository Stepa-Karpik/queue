from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Role
from bot.services.import_list import parse_excel, parse_text_list
from bot.services.roster import add_students_to_group
from bot.services.users import get_effective_group, get_user_by_tg, is_admin_mode
from bot.states.list_import import ListImportStates

router = Router()


@router.message(Command("list"))
async def list_start(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or (user.role != Role.STAROSTA.value and not is_admin_mode(user)):
        await message.answer("Команда доступна только старосте или админу.")
        return

    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Сначала выберите группу.")
        return

    await state.clear()
    await message.answer(f"Отправьте список студентов для группы {group.name} (текст, .txt или .xlsx).")
    await state.set_state(ListImportStates.waiting_list)


@router.message(ListImportStates.waiting_list)
async def list_upload(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if not user or (user.role != Role.STAROSTA.value and not is_admin_mode(user)):
        await message.answer("Команда доступна только старосте или админу.")
        await state.clear()
        return

    group = await get_effective_group(session, user)
    if not group:
        await message.answer("Не удалось определить группу.")
        await state.clear()
        return

    if group.roster_loaded:
        await message.answer("Список уже загружен. Ничего не изменено.")
        await state.clear()
        return

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

    await message.answer(f"Загружено студентов в группу {group.name}: {count}")
    await state.clear()
