from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_last_name = State()
    waiting_last_name_confirm = State()
    waiting_full_name = State()
    waiting_full_name_confirm = State()
    waiting_self_full_name = State()
    waiting_self_faculty = State()
    waiting_self_group = State()
    waiting_self_starosta = State()
