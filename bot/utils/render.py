from __future__ import annotations

from typing import Iterable


def keycap_number(number: int) -> str:
    keycaps = {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟",
    }
    return keycaps.get(number, str(number))


def render_work_row(work_numbers: Iterable[int], submitted: Iterable[int]) -> str:
    submitted_set = set(submitted)
    items = []
    for number in work_numbers:
        if number in submitted_set:
            items.append("🟩")
        else:
            items.append(keycap_number(number))
    return " ".join(items)


def render_progress_bar(completed: int, total: int, width: int = 6) -> str:
    if total <= 0:
        return "░" * width

    filled = round((completed / total) * width)
    if completed > 0:
        filled = max(1, filled)
    filled = min(width, max(0, filled))
    return f"{'█' * filled}{'░' * (width - filled)}"


def score_to_grade(avg_score: float) -> int:
    if avg_score < 61:
        return 2
    if avg_score < 76:
        return 3
    if avg_score < 91:
        return 4
    return 5
