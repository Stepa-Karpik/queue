from aiogram.fsm.state import State, StatesGroup


class AdminPanelStates(StatesGroup):
    waiting_broadcast_text = State()
