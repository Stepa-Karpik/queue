from __future__ import annotations

from typing import Iterable


def render_work_row(total: int, submitted: Iterable[int]) -> str:
    submitted_set = set(submitted)
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
    items = []
    for i in range(1, total + 1):
        if i in submitted_set:
            items.append("🟩")
        else:
            items.append(keycaps.get(i, str(i)))
    return " ".join(items)


def score_to_grade(avg_score: float) -> int:
    if avg_score < 61:
        return 2
    if avg_score < 76:
        return 3
    if avg_score < 91:
        return 4
    return 5
