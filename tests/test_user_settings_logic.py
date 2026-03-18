import unittest

from bot.utils.teacher_names import normalize_teacher_entries, normalize_teacher_names
from bot.utils.user_settings import (
    NotificationMode,
    get_notification_mode_description,
    should_send_subject_notification,
)


class UserSettingsLogicTests(unittest.TestCase):
    def test_enabled_notifications_send_everything(self):
        self.assertTrue(
            should_send_subject_notification(
                NotificationMode.ENABLED.value,
                group_subject_id=10,
                has_pending_work=False,
                manual_subject_ids=set(),
            )
        )

    def test_disabled_notifications_send_nothing(self):
        self.assertFalse(
            should_send_subject_notification(
                NotificationMode.DISABLED.value,
                group_subject_id=10,
                has_pending_work=True,
                manual_subject_ids={10},
            )
        )

    def test_auto_notifications_only_for_pending_subjects(self):
        self.assertTrue(
            should_send_subject_notification(
                NotificationMode.AUTO.value,
                group_subject_id=10,
                has_pending_work=True,
                manual_subject_ids=set(),
            )
        )
        self.assertFalse(
            should_send_subject_notification(
                NotificationMode.AUTO.value,
                group_subject_id=10,
                has_pending_work=False,
                manual_subject_ids=set(),
            )
        )

    def test_manual_notifications_only_for_selected_subjects(self):
        self.assertTrue(
            should_send_subject_notification(
                NotificationMode.MANUAL.value,
                group_subject_id=10,
                has_pending_work=False,
                manual_subject_ids={10, 11},
            )
        )
        self.assertFalse(
            should_send_subject_notification(
                NotificationMode.MANUAL.value,
                group_subject_id=12,
                has_pending_work=True,
                manual_subject_ids={10, 11},
            )
        )

    def test_notification_mode_descriptions_exist(self):
        for mode in NotificationMode:
            self.assertTrue(get_notification_mode_description(mode.value))

    def test_normalize_teacher_names_deduplicates_and_cleans(self):
        self.assertEqual(
            normalize_teacher_names(
                [
                    " доц. Иванов  Иван Иванович ",
                    "Иванов Иван Иванович",
                    "",
                    "ст.пр. Петров Петр Петрович",
                ]
            ),
            ["Иванов Иван Иванович", "Петров Петр Петрович"],
        )

    def test_normalize_teacher_entries_formats_as_subject_and_name(self):
        self.assertEqual(
            normalize_teacher_entries(
                [
                    ("Базы данных", "доц. Иванов Иван Иванович"),
                    ("Базы данных", "Иванов Иван Иванович"),
                    ("Программирование", "асс. Петров Петр Петрович"),
                ]
            ),
            [
                "Базы данных\nИванов Иван Иванович",
                "Программирование\nПетров Петр Петрович",
            ],
        )


if __name__ == "__main__":
    unittest.main()
