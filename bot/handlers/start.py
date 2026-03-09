from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import HELP_ALIASES, confirm_kb, main_menu_kb
from bot.models import Role
from bot.services.students import find_students_by_last_name, find_student_by_full_name, get_student_group
from bot.services.roster import get_or_create_faculty, get_or_create_group
from bot.services.users import get_user_by_tg, ensure_user
from bot.states.registration import RegistrationStates
from bot.utils.names import format_full_name, split_full_name, normalize_name
from bot.keyboards.callbacks import ConfirmCallback
from bot.models import Student

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg(session, message.from_user.id)
    if user and user.student_id:
        is_starosta = user.role == Role.STAROSTA.value
        await message.answer(
            "Вы уже зарегистрированы.\nВыберите действие в меню ниже.",
            reply_markup=main_menu_kb(is_starosta=is_starosta),
        )
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
    students = await find_students_by_last_name(session, message.text)
    if not students:
        await message.answer(
            "Фамилия не найдена в списке.\n"
            "Введите полное ФИО для самостоятельной регистрации."
        )
        await state.set_state(RegistrationStates.waiting_self_full_name)
        return
    if len(students) > 1:
        names = "\n".join(format_full_name(s.last_name, s.first_name, s.middle_name) for s in students)
        await message.answer(f"Найдено несколько совпадений:\n{names}\n\nВведите полное ФИО полностью.")
        await state.set_state(RegistrationStates.waiting_full_name)
        return

    student = students[0]
    group = await get_student_group(session, student.id)
    group_name = group.name if group else "—"
    full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
    await state.update_data(candidate_id=student.id)
    await message.answer(f"{full_name}. {group_name}, верно?", reply_markup=confirm_kb("confirm_student", str(student.id)))
    await state.set_state(RegistrationStates.waiting_last_name_confirm)


@router.message(RegistrationStates.waiting_full_name)
async def full_name_handler(message: Message, state: FSMContext, session: AsyncSession):
    students = await find_student_by_full_name(session, message.text)
    if not students:
        await message.answer(
            "Студент не найден в списке.\n"
            "Перейдём к самостоятельной регистрации. Введите полное ФИО."
        )
        await state.set_state(RegistrationStates.waiting_self_full_name)
        return
    if len(students) > 1:
        await message.answer("Найдено несколько совпадений. Обратитесь к администратору @Karpov_Stepan.")
        await state.clear()
        return

    student = students[0]
    group = await get_student_group(session, student.id)
    group_name = group.name if group else "—"
    full_name = format_full_name(student.last_name, student.first_name, student.middle_name)
    await state.update_data(candidate_id=student.id)
    await message.answer(f"{full_name}. {group_name}, верно?", reply_markup=confirm_kb("confirm_student", str(student.id)))
    await state.set_state(RegistrationStates.waiting_full_name_confirm)


@router.callback_query(ConfirmCallback.filter(F.action == "confirm_student"))
async def confirm_student(call: CallbackQuery, callback_data: ConfirmCallback, state: FSMContext, session: AsyncSession):
    await call.answer()
    if callback_data.value == "no":
        data = await state.get_data()
        if data.get("rejected_once"):
            await call.message.answer("Обратитесь к администратору @Karpov_Stepan или попробуйте позже")
            await state.clear()
            return
        await state.update_data(rejected_once=True)
        await call.message.answer("Введите полное ФИО.")
        await state.set_state(RegistrationStates.waiting_full_name)
        return

    student_id = int(callback_data.value)
    await ensure_user(
        session,
        tg_id=call.from_user.id,
        username=call.from_user.username,
        student_id=student_id,
        role=Role.STUDENT,
    )
    await call.message.answer(
        "Регистрация успешна.\nВыберите действие в меню.",
        reply_markup=main_menu_kb(is_starosta=False),
    )
    await state.clear()


@router.message(RegistrationStates.waiting_self_full_name)
async def self_full_name(message: Message, state: FSMContext):
    try:
        last, first, middle = split_full_name(message.text)
    except ValueError:
        await message.answer(
            "Неверный формат.\n"
            "Введите ФИО так: Фамилия Имя Отчество (отчество необязательно)."
        )
        return
    await state.update_data(self_last=last, self_first=first, self_middle=middle)
    await message.answer("Шаг 2 из 3: введите факультет.")
    await state.set_state(RegistrationStates.waiting_self_faculty)


@router.message(RegistrationStates.waiting_self_faculty)
async def self_faculty(message: Message, state: FSMContext):
    await state.update_data(self_faculty=normalize_name(message.text))
    await message.answer("Шаг 3 из 3: введите группу.")
    await state.set_state(RegistrationStates.waiting_self_group)


@router.message(RegistrationStates.waiting_self_group)
async def self_group(message: Message, state: FSMContext):
    await state.update_data(self_group=normalize_name(message.text))
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
    await call.message.answer(
        "Регистрация завершена.\nТеперь можно работать через кнопки меню.",
        reply_markup=main_menu_kb(is_starosta=role == Role.STAROSTA),
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
        "4. Кнопка «⬅️ Главное меню» всегда возвращает на стартовый экран.",
    ]
    if user and user.role == Role.STAROSTA.value:
        lines.append("5. Кнопка «🛠 Староста» открывает режим управления дисциплинами и пользователями.")
        lines.append("6. Команда /list загружает список группы.")
    is_starosta = bool(user and user.role == Role.STAROSTA.value)
    await message.answer("\n".join(lines), reply_markup=main_menu_kb(is_starosta=is_starosta))
