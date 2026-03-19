import unittest

from bot.utils.names import (
    get_group_validation_error_text,
    normalize_group_name,
    normalize_valid_group_name,
)


class GroupNamesTests(unittest.TestCase):
    def test_valid_group_name_is_normalized_to_uppercase(self):
        self.assertEqual(normalize_valid_group_name("ви23"), "ВИ23")
        self.assertEqual(normalize_valid_group_name("ВИАС33"), "ВИАС33")
        self.assertEqual(normalize_valid_group_name("вкб21"), "ВКБ21")

    def test_invalid_group_names_are_rejected(self):
        self.assertIsNone(normalize_valid_group_name("ВИ-21"))
        self.assertIsNone(normalize_valid_group_name("ВИ 21"))
        self.assertIsNone(normalize_valid_group_name("👥 ГРУППА"))
        self.assertIsNone(normalize_valid_group_name("📆РАСПИСАНИЕ"))
        self.assertIsNone(normalize_valid_group_name("ПРАКТИЧЕСКИЕ"))
        self.assertIsNone(normalize_valid_group_name("23ВИ"))

    def test_plain_normalization_is_left_unchanged_for_existing_usage(self):
        self.assertEqual(normalize_group_name("ви-21"), "ВИ-21")

    def test_group_validation_error_mentions_valid_examples(self):
        text = get_group_validation_error_text()
        self.assertIn("ВИ23", text)
        self.assertIn("ВКБ21", text)
        self.assertIn("ВИАС33", text)


if __name__ == "__main__":
    unittest.main()
