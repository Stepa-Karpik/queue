from aiogram.fsm.state import State, StatesGroup


class ManagementStates(StatesGroup):
    viewing_panel = State()
    waiting_add_subject_name = State()
    waiting_add_subject_count = State()
    waiting_rename_subject = State()
    waiting_add_user_full_name = State()
    waiting_edit_user_full_name = State()
    waiting_submission_score = State()
