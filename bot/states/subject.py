from aiogram.fsm.state import State, StatesGroup


class SubjectStates(StatesGroup):
    viewing_subject = State()
    marking_work = State()
    entering_score = State()
