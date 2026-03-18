import unittest

from bot.utils.notification_filters import get_students_with_pending_works


class NotificationFiltersTests(unittest.TestCase):
    def test_returns_only_students_with_incomplete_subject(self):
        items = [
            {"student_id": 1, "completed": 2, "total": 3, "is_inactive": False},
            {"student_id": 2, "completed": 3, "total": 3, "is_inactive": False},
            {"student_id": 3, "completed": 1, "total": 4, "is_inactive": True},
            {"student_id": 4, "completed": 0, "total": 0, "is_inactive": False},
        ]

        self.assertEqual(get_students_with_pending_works(items), {1})


if __name__ == "__main__":
    unittest.main()
