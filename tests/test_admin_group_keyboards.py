import unittest

from bot.keyboards.admin import admin_group_edit_kb, admin_group_settings_kb, admin_groups_kb


class AdminGroupKeyboardsTests(unittest.TestCase):
    def test_groups_keyboard_opens_group_settings_and_has_add_button(self):
        keyboard = admin_groups_kb([(7, "ИКБО-01-23 • ИТ")], page=1, total_pages=1)

        self.assertEqual(keyboard.inline_keyboard[0][0].text, "ИКБО-01-23 • ИТ")
        self.assertIn("group_view", keyboard.inline_keyboard[0][0].callback_data)

        add_button = keyboard.inline_keyboard[1][0]
        self.assertIn("Добавить", add_button.text)
        self.assertIn("group_add", add_button.callback_data)

    def test_group_settings_keyboard_has_required_actions(self):
        keyboard = admin_group_settings_kb(group_id=7)
        texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("Выбрать", " ".join(texts))
        self.assertIn("Изменить", " ".join(texts))
        self.assertIn("Удалить", " ".join(texts))
        self.assertIn("Добавить", " ".join(texts))
        self.assertIn("Назад", " ".join(texts))

    def test_group_edit_keyboard_has_people_name_and_faculty_actions(self):
        keyboard = admin_group_edit_kb(group_id=7)
        texts = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("Люди", " ".join(texts))
        self.assertIn("Название", " ".join(texts))
        self.assertIn("Факультет", " ".join(texts))
        self.assertIn("Назад", " ".join(texts))


if __name__ == "__main__":
    unittest.main()
