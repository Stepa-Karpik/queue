import unittest

from bot.handlers.schedule import _week_image_path
from bot.models import ScheduleWeekType


class ScheduleWeekMediaTests(unittest.TestCase):
    def test_lower_week_uses_bottom_image(self):
        path = _week_image_path(ScheduleWeekType.LOWER)
        self.assertTrue(str(path).endswith("media\\bottom_week.png") or str(path).endswith("media/bottom_week.png"))

    def test_upper_week_uses_top_image(self):
        path = _week_image_path(ScheduleWeekType.UPPER)
        self.assertTrue(str(path).endswith("media\\top_week.png") or str(path).endswith("media/top_week.png"))


if __name__ == "__main__":
    unittest.main()
