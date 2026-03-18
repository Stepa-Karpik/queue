import unittest

from bot.utils.teacher_names import normalize_teacher_name, render_teacher_records


class TeacherNamesTests(unittest.TestCase):
    def test_normalize_teacher_name_strips_prefix_without_space(self):
        self.assertEqual(
            normalize_teacher_name("асс.Мозговой Николай Васильевич"),
            "Мозговой Николай Васильевич",
        )
        self.assertEqual(
            normalize_teacher_name("доц.Рухленко Сергей Анатольевич"),
            "Рухленко Сергей Анатольевич",
        )

    def test_render_teacher_records_groups_by_subject_and_labels_lesson_type(self):
        self.assertEqual(
            render_teacher_records(
                [
                    (
                        "Алгоритмы и структуры данных",
                        "lab",
                        "асс.Мозговой Николай Васильевич",
                    ),
                    (
                        "Алгоритмы и структуры данных",
                        "lecture",
                        "доц.Рухленко Сергей Анатольевич",
                    ),
                    (
                        "Базы данных",
                        "practice",
                        "преп. Котов Алексей Сергеевич",
                    ),
                ]
            ),
            [
                "Алгоритмы и структуры данных\nЛек. Рухленко Сергей Анатольевич\nЛаб. Мозговой Николай Васильевич",
                "Базы данных\nПр. Котов Алексей Сергеевич",
            ],
        )

    def test_render_teacher_records_deduplicates_same_teacher_inside_slot(self):
        self.assertEqual(
            render_teacher_records(
                [
                    (
                        "Алгоритмы и структуры данных",
                        "lab",
                        "асс. Мозговой Николай Васильевич",
                    ),
                    (
                        "Алгоритмы и структуры данных",
                        "lab",
                        "Мозговой Николай Васильевич",
                    ),
                ]
            ),
            [
                "Алгоритмы и структуры данных\nЛаб. Мозговой Николай Васильевич",
            ],
        )


if __name__ == "__main__":
    unittest.main()
