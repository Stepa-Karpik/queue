from aiogram.filters.callback_data import CallbackData


class ConfirmCallback(CallbackData, prefix="confirm"):
    action: str
    value: str


class SubjectCallback(CallbackData, prefix="subject"):
    group_subject_id: int
    kind: str


class SortCallback(CallbackData, prefix="sort"):
    by: str


class WorkCallback(CallbackData, prefix="work"):
    number: int


class StudentCallback(CallbackData, prefix="student"):
    student_id: int


class ActionCallback(CallbackData, prefix="action"):
    name: str


class PageCallback(CallbackData, prefix="page"):
    action: str
    page: int


class AdminWorkCallback(CallbackData, prefix="admin_work"):
    action: str
    number: int


class AddSubjectCallback(CallbackData, prefix="add_subject"):
    kind: str
