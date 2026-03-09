from aiogram.fsm.state import State, StatesGroup


class ListImportStates(StatesGroup):
    waiting_faculty = State()
    waiting_group = State()
    waiting_list = State()
