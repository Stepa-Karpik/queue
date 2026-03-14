from aiogram.fsm.state import State, StatesGroup


class AdminPanelStates(StatesGroup):
    waiting_broadcast_text = State()
    waiting_user_full_name = State()
