import unittest

from bot.keyboards.common import works_kb


class SubjectWorkKeyboardTests(unittest.TestCase):
    def test_submitted_work_button_is_clickable_for_cancellation(self):
        keyboard = works_kb([1, 2], submitted_numbers=[2])

        submitted_button = keyboard.inline_keyboard[0][1]
        self.assertEqual(submitted_button.text, "🟩")
        self.assertNotIn("noop", submitted_button.callback_data)


if __name__ == "__main__":
    unittest.main()
