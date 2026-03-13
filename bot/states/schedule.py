from aiogram.fsm.state import State, StatesGroup


class ScheduleStates(StatesGroup):
    waiting_lower_week_file = State()
    waiting_upper_week_file = State()
