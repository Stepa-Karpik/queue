import unittest

from bot.utils.names import normalize_faculty_name


class FacultyNamesTests(unittest.TestCase):
    def test_normalize_faculty_name_uses_uppercase(self):
        self.assertEqual(normalize_faculty_name(" амиу "), "АМИУ")

    def test_iivt_aliases_collapse_to_single_value(self):
        self.assertEqual(normalize_faculty_name("ИиВТ"), "ИИВТ")
        self.assertEqual(normalize_faculty_name("ИИВТ"), "ИИВТ")
        self.assertEqual(normalize_faculty_name("иивт"), "ИИВТ")
        self.assertEqual(normalize_faculty_name("ИВТ"), "ИИВТ")
        self.assertEqual(normalize_faculty_name("И И В Т"), "ИИВТ")


if __name__ == "__main__":
    unittest.main()
