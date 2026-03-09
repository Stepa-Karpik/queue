from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_add_subject = State()
    waiting_remove_subject = State()
    waiting_add_work = State()
    waiting_remove_work = State()
    waiting_add_subject_name = State()
    waiting_add_subject_count = State()
