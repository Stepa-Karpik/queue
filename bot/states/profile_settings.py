from aiogram.fsm.state import State, StatesGroup


class ProfileSettingsStates(StatesGroup):
    waiting_full_name = State()
    waiting_group = State()
    waiting_faculty = State()
    waiting_group_after_faculty = State()
