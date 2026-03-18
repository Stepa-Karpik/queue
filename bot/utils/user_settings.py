from __future__ import annotations

from enum import Enum


class NotificationMode(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    AUTO = "auto"
    MANUAL = "manual"


def get_notification_mode_label(mode: str) -> str:
    return {
        NotificationMode.ENABLED.value: "Включены",
        NotificationMode.DISABLED.value: "Выключены",
        NotificationMode.AUTO.value: "Автоматически",
        NotificationMode.MANUAL.value: "Вручную",
    }.get(mode, "Автоматически")


def get_notification_mode_description(mode: str) -> str:
    return {
        NotificationMode.ENABLED.value: "Включены — бот присылает уведомления по всем дисциплинам вашей группы.",
        NotificationMode.DISABLED.value: "Выключены — бот не присылает уведомления о занятиях.",
        NotificationMode.AUTO.value: "Автоматически — бот напоминает только о тех дисциплинах, где у вас еще остались несданные работы.",
        NotificationMode.MANUAL.value: "Вручную — вы сами выбираете дисциплины, по которым хотите получать уведомления.",
    }.get(mode, "Автоматически — бот напоминает только о незавершенных дисциплинах.")


def should_send_subject_notification(
    mode: str,
    *,
    group_subject_id: int,
    has_pending_work: bool,
    manual_subject_ids: set[int] | None,
) -> bool:
    if mode == NotificationMode.DISABLED.value:
        return False
    if mode == NotificationMode.ENABLED.value:
        return True
    if mode == NotificationMode.MANUAL.value:
        return group_subject_id in (manual_subject_ids or set())
    return has_pending_work
