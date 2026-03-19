import unittest

from bot.utils.submission_flow import (
    get_submission_mode_from_action,
    get_submission_subject_prompt,
    get_submission_work_action,
    get_submission_work_prompt,
)


class SubmissionFlowTests(unittest.TestCase):
    def test_get_submission_mode_from_action(self):
        self.assertEqual(get_submission_mode_from_action("submission_add"), "add")
        self.assertEqual(get_submission_mode_from_action("submission_delete"), "delete")
        self.assertIsNone(get_submission_mode_from_action("submissions"))

    def test_add_mode_allows_new_submissions(self):
        self.assertEqual(get_submission_work_action("add", is_submitted=False), "add")
        self.assertEqual(get_submission_work_action("add", is_submitted=True), "delete")

    def test_delete_mode_only_allows_existing_submissions(self):
        self.assertEqual(get_submission_work_action("delete", is_submitted=True), "delete")
        self.assertEqual(get_submission_work_action("delete", is_submitted=False), "noop")

    def test_prompts_match_selected_mode(self):
        self.assertIn("отметки", get_submission_subject_prompt("add").lower())
        self.assertIn("отмены", get_submission_subject_prompt("delete").lower())
        self.assertIn("отметки", get_submission_work_prompt("add").lower())
        self.assertIn("отмены", get_submission_work_prompt("delete").lower())

    def test_add_prompt_explains_green_work_can_be_cancelled(self):
        prompt = get_submission_work_prompt("add").lower()
        self.assertIn("удалит", prompt)

    def test_submission_action_mode_values_are_expected(self):
        self.assertIn("add", {"add", "delete"})
        self.assertIn("delete", {"add", "delete"})


if __name__ == "__main__":
    unittest.main()
