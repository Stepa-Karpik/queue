from __future__ import annotations

from typing import Literal

SubmissionMode = Literal["add", "delete"]


def get_submission_mode_from_action(action: str) -> SubmissionMode | None:
    if action == "submission_add":
        return "add"
    if action == "submission_delete":
        return "delete"
    return None


def get_submission_subject_prompt(mode: SubmissionMode) -> str:
    if mode == "delete":
        return "Выберите дисциплину для отмены сдачи:"
    return "Выберите дисциплину для отметки сдачи:"


def get_submission_work_prompt(mode: SubmissionMode) -> str:
    if mode == "delete":
        return (
            "Выберите номер работы для отмены сдачи:\n"
            "🟥 — работа уже отмечена, нажатие удалит сдачу.\n"
            "1️⃣ — сдачи нет, кнопка недоступна."
        )
    return (
        "Выберите номер работы для отметки:\n"
        "🟩 — работа уже отмечена, нажатие удалит сдачу.\n"
        "1️⃣ — сдачи нет, нажатие добавит ее."
    )


def get_submission_work_action(mode: SubmissionMode, *, is_submitted: bool) -> str:
    if mode == "delete":
        return "delete" if is_submitted else "noop"
    return "delete" if is_submitted else "add"
