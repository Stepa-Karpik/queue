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


class StarostaMenuCallback(CallbackData, prefix="st_menu"):
    section: str
    action: str


class StarostaSubjectCallback(CallbackData, prefix="st_subject"):
    mode: str
    group_subject_id: int


class StarostaStudentCallback(CallbackData, prefix="st_student"):
    mode: str
    student_id: int


class StarostaPageCallback(CallbackData, prefix="st_page"):
    section: str
    mode: str
    page: int


class StarostaRoleCallback(CallbackData, prefix="st_role"):
    student_id: int
    role: str


class StarostaWorkCallback(CallbackData, prefix="st_work"):
    action: str
    number: int


class ManageMenuCallback(CallbackData, prefix="mg_menu"):
    section: str
    action: str


class ManageStudentCallback(CallbackData, prefix="mg_student"):
    action: str
    student_id: int


class ManageSubjectCallback(CallbackData, prefix="mg_subject"):
    action: str
    group_subject_id: int


class ManagePageCallback(CallbackData, prefix="mg_page"):
    section: str
    page: int


class ManageRoleCallback(CallbackData, prefix="mg_role"):
    student_id: int
    role: str


class ManageSubmissionCallback(CallbackData, prefix="mg_submit"):
    action: str
    value: int


class ManageSubmissionActionCallback(CallbackData, prefix="mg_submit_action"):
    mode: str
    student_id: int


class ManageSubmissionSubjectCallback(CallbackData, prefix="mg_submit_subject"):
    mode: str
    student_id: int
    group_subject_id: int


class ManageSubmissionWorkCallback(CallbackData, prefix="mg_submit_work"):
    mode: str
    student_id: int
    group_subject_id: int
    work_number: int


class ManageRemoveWorkCallback(CallbackData, prefix="mg_remove_work"):
    group_subject_id: int
    work_number: int


class AdminPanelCallback(CallbackData, prefix="ad_panel"):
    action: str
    value: str


class ScheduleCallback(CallbackData, prefix="schedule"):
    action: str
    value: str
