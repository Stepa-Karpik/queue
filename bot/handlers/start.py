from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.callbacks import ConfirmCallback
from bot.keyboards.common import HELP_ALIASES, confirm_kb, main_menu_kb
from bot.models import Role, Student
from bot.services.roster import get_or_create_faculty, get_or_create_group
from bot.services.students import find_student_by_full_name, find_students_by_last_name, get_student_group
from bot.services.users import ensure_user, get_user_by_student, get_user_by_tg, is_admin_mode, is_admin_user
from bot.states.registration import RegistrationStates
from bot.utils.names import (
    format_full_name,
    get_group_validation_error_text,
    normalize_faculty_name,
    normalize_group_name,
    normalize_name,
    normalize_valid_group_name,
    split_full_name,
)

router = Router()


async def _send_main_menu(message: Message, user) -> None:
    is_starosta = bool(user and user.role == Role.STAROSTA.value)
    is_admin = is_admin_user(user)
    await message.answer(
        "Выберите действие в меню ниже.",
        reply_markup=main_menu_kb(
            is_starosta=is_starosta,
            is_admin=is_admin,
            admin_mode=is_admin_mode(user),
        ),
    )


async def _ensure_student_available(session: AsyncSession, student: Student, tg_id: int) -> tuple[bool, str | None]:
    linked_user = await get_user_by_student(session, student.id)
    if linked_user and linked_user.tg_id != tg_id:
        return False, "Пока-пока, ты пытаешься залезть не туда."
    return True, None


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if user and user.student_id:
        await message.answer("Вы уже зарегистрированы.")
        await _send_main_menu(message, user)
        return

    await state.clear()
    await message.answer(
        "Добро пожаловать.\n"
        "Шаг 1 из 3: введите вашу фамилию.\n"
        "Регистр не важен.",
    )
    await state.set_state(RegistrationStates.waiting_last_name)


@router.message(RegistrationStates.waiting_last_name)
async def last_name_handler(message: Message, state: FSMContext, session: AsyncSession):
    students = await find_students_by_last_name(session, message.text or "")
    if not students:
        await message.answer(
            "Фамилия не найдена в списке.\n"
            "Введите полное ФИО для самостоятельной регистрации."
        )
        await state.set_state(RegistrationStates.waiting_self_full_name)
        return

    await message.answer("Найден пользователь с такой фамилией. Для проверки введите полное ФИО.")
    await state.set_state(RegistrationStates.waiting_full_name)


@router.message(RegistrationStates.waiting_full_name)
async def full_name_handler(message: Message, state: FSMContext, session: AsyncSession):
    students = await find_student_by_full_name(session, message.text or "")
    if not students:
        await message.answer(
            "Студент не найден в списке.\n"
            "Переходим к самостоятельной регистрации. Введите полное ФИО."
        )
        await state.set_state(RegistrationStates.waiting_self_full_name)
        return
    if len(students) > 1:
        await message.answer("Найдено несколько совпадений. Обратитесь к администратору.")
        await state.clear()
        return

    student = students[0]
    is_available, error_text = await _ensure_student_available(session, student, message.from_user.id)
    if not is_available:
        await message.answer(error_text)
        await state.clear()
        return

    await state.update_data(candidate_id=student.id)
    group = await get_student_group(session, student.id)
    group_name = normalize_group_name(group.name) if group else "—"
    await message.answer(
        f"{format_full_name(student.last_name, student.first_name, student.middle_name)}. {group_name}, верно?",
        reply_markup=confirm_kb("confirm_student", str(student.id)),
    )
    await state.set_state(RegistrationStates.waiting_full_name_confirm)


@router.callback_query(ConfirmCallback.filter(F.action == "confirm_student"))
async def confirm_student(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if callback_data.value == "no":
        await call.message.answer("Введите полное ФИО.")
        await state.set_state(RegistrationStates.waiting_full_name)
        return

    student_id = int(callback_data.value)
    student = await session.get(Student, student_id)
    if not student:
        await call.message.answer("Профиль не найден. Начните заново через /start.")
        await state.clear()
        return

    is_available, error_text = await _ensure_student_available(session, student, call.from_user.id)
    if not is_available:
        await call.message.answer(error_text)
        await state.clear()
        return

    await ensure_user(
        session,
        tg_id=call.from_user.id,
        username=call.from_user.username,
        student_id=student_id,
        role=Role.STUDENT,
    )
    user = await get_user_by_tg(session, call.from_user.id)
    await call.message.answer("Регистрация успешна.")
    await call.message.answer(
        "Теперь можно работать через кнопки меню.",
        reply_markup=main_menu_kb(
            is_starosta=False,
            is_admin=is_admin_user(user),
            admin_mode=is_admin_mode(user),
        ),
    )
    await state.clear()


@router.message(RegistrationStates.waiting_self_full_name)
async def self_full_name(message: Message, state: FSMContext):
    try:
        last, first, middle = split_full_name(message.text or "")
    except ValueError:
        await message.answer(
            "Неверный формат.\n"
            "Введите ФИО так: Фамилия Имя Отчество (отчество необязательно)."
        )
        return
    await state.update_data(self_last=last, self_first=first, self_middle=middle)
    await message.answer("Шаг 2 из 3: введите факультет в формате ИиВТ, АМИУ и тд.")
    await state.set_state(RegistrationStates.waiting_self_faculty)


@router.message(RegistrationStates.waiting_self_faculty)
async def self_faculty(message: Message, state: FSMContext):
    await state.update_data(self_faculty=normalize_faculty_name(message.text or ""))
    await message.answer("Шаг 3 из 3: введите группу в формате ВКБ21, ВИАС33, ВИ23 и тд.")
    await state.set_state(RegistrationStates.waiting_self_group)


@router.message(RegistrationStates.waiting_self_group)
async def self_group(message: Message, state: FSMContext):
    group_name = normalize_valid_group_name(message.text or "")
    if not group_name:
        await message.answer(get_group_validation_error_text())
        return
    await state.update_data(self_group=group_name)
    await message.answer(
        "Вы староста группы?",
        reply_markup=confirm_kb("self_starosta", "yes"),
    )
    await state.set_state(RegistrationStates.waiting_self_starosta)


@router.callback_query(ConfirmCallback.filter(F.action == "self_starosta"))
async def self_starosta_confirm(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    data = await state.get_data()
    last = data.get("self_last")
    first = data.get("self_first")
    middle = data.get("self_middle")
    faculty_name = data.get("self_faculty")
    group_name = data.get("self_group")
    if not all([last, first, faculty_name, group_name]):
        await call.message.answer("Недостаточно данных для регистрации. Начните снова через /start.")
        await state.clear()
        return

    faculty = await get_or_create_faculty(session, faculty_name)
    group = await get_or_create_group(session, group_name, faculty.id)

    existing = await find_student_by_full_name(session, f"{last} {first} {middle or ''}".strip())
    if existing:
        student = existing[0]
        is_available, error_text = await _ensure_student_available(session, student, call.from_user.id)
        if not is_available:
            await call.message.answer(error_text)
            await state.clear()
            return
    else:
        student = Student(last_name=last, first_name=first, middle_name=middle, group_id=group.id)
        session.add(student)
        await session.commit()
        await session.refresh(student)

    role = Role.STAROSTA if callback_data.value != "no" else Role.STUDENT
    await ensure_user(
        session,
        tg_id=call.from_user.id,
        username=call.from_user.username,
        student_id=student.id,
        role=role,
    )
    user = await get_user_by_tg(session, call.from_user.id)
    await call.message.answer(
        "Регистрация завершена.\nТеперь можно работать через кнопки меню.",
        reply_markup=main_menu_kb(
            is_starosta=role == Role.STAROSTA,
            is_admin=is_admin_user(user),
            admin_mode=is_admin_mode(user),
        ),
    )
    await state.clear()


@router.message(Command("help"))
@router.message(F.text.in_(HELP_ALIASES))
async def help_handler(message: Message, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    lines = [
        "Как пользоваться ботом:",
        "1. Нажмите «🧪 Лабораторные» или «📝 Практические».",
        "2. Выберите дисциплину.",
        "3. Внутри дисциплины используйте кнопки: сортировка, отметка сдачи, статистика.",
        "4. Кнопка «✅ Отметить сдачу» отмечает только ваши работы.",
        "5. Кнопка «👥 Список группы» показывает состав группы по алфавиту.",
        "6. Кнопка «📆 Расписание» открывает расписание вашей группы.",
        "7. Кнопка «⬅️ Главное меню» всегда возвращает на стартовый экран.",
    ]
    if user and user.role == Role.STAROSTA.value:
        lines.append("8. Кнопка «🛠 Староста» открывает режим управления дисциплинами, пользователями и сдачами своей группы.")
        lines.append("9. Команда /list загружает список своей группы.")
    if is_admin_user(user):
        lines.append("10. Кнопка «👑 Админ» включает отдельный режим администратора с другой клавиатурой.")
        lines.append("11. В админ-режиме доступны выбор любой группы, просмотр всех пользователей, рассылка, расписание и меню «Староста».")
    await message.answer(
        "\n".join(lines),
        reply_markup=main_menu_kb(
            is_starosta=bool(user and user.role == Role.STAROSTA.value),
            is_admin=is_admin_user(user),
            admin_mode=is_admin_mode(user),
        ),
    )
