from aiogram.fsm.state import State, StatesGroup


class ListImportStates(StatesGroup):
    waiting_list = State()
