from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def get_students_with_pending_works(priority_items: Iterable[Mapping[str, Any]]) -> set[int]:
    pending_student_ids: set[int] = set()
    for item in priority_items:
        if item.get("is_inactive"):
            continue
        completed = int(item.get("completed", 0) or 0)
        total = int(item.get("total", 0) or 0)
        if total <= 0:
            continue
        if completed < total:
            pending_student_ids.add(int(item["student_id"]))
    return pending_student_ids
