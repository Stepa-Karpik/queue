from __future__ import annotations

import re
from collections import defaultdict

from bot.utils.names import normalize_compare_text, normalize_name

TEACHER_PREFIX_RE = re.compile(
    r"^\s*(?:асс\.?|доц\.?|преп\.?|ст\.?\s*пр\.?)\s*",
    flags=re.IGNORECASE,
)

LESSON_TYPE_ORDER = {
    "lecture": 0,
    "lab": 1,
    "practice": 2,
    "other": 3,
}

LESSON_TYPE_LABELS = {
    "lecture": "Лек.",
    "lab": "Лаб.",
    "practice": "Пр.",
    "other": "Зан.",
}


def _compare_key(value: str) -> str:
    return normalize_compare_text(value).lower()


def normalize_teacher_name(name: str) -> str:
    cleaned = normalize_name(name or "")
    while cleaned:
        updated = TEACHER_PREFIX_RE.sub("", cleaned).strip()
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned


def normalize_teacher_names(names: list[str]) -> list[str]:
    unique_names: dict[str, str] = {}
    for raw_name in names:
        cleaned = normalize_teacher_name(raw_name or "")
        if not cleaned:
            continue
        unique_names.setdefault(_compare_key(cleaned), cleaned)
    return sorted(unique_names.values(), key=_compare_key)


def teacher_lesson_type_label(lesson_type: str) -> str:
    return LESSON_TYPE_LABELS.get((lesson_type or "").strip().lower(), LESSON_TYPE_LABELS["other"])


def normalize_teacher_records(entries: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    unique_records: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for discipline, lesson_type, teacher_name in entries:
        cleaned_discipline = normalize_name(discipline or "")
        cleaned_lesson_type = (lesson_type or "").strip().lower()
        cleaned_teacher = normalize_teacher_name(teacher_name or "")
        if not cleaned_discipline or not cleaned_teacher:
            continue
        compare_key = (
            _compare_key(cleaned_discipline),
            cleaned_lesson_type,
            _compare_key(cleaned_teacher),
        )
        unique_records.setdefault(compare_key, (cleaned_discipline, cleaned_lesson_type, cleaned_teacher))

    return sorted(
        unique_records.values(),
        key=lambda item: (
            _compare_key(item[0]),
            LESSON_TYPE_ORDER.get(item[1], LESSON_TYPE_ORDER["other"]),
            _compare_key(item[2]),
        ),
    )


def render_teacher_records(entries: list[tuple[str, str, str]]) -> list[str]:
    normalized = normalize_teacher_records(entries)
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for discipline, lesson_type, teacher_name in normalized:
        grouped[discipline].append((lesson_type, teacher_name))

    rendered_blocks: list[str] = []
    for discipline in sorted(grouped.keys(), key=_compare_key):
        lines = [discipline]
        for lesson_type, teacher_name in sorted(
            grouped[discipline],
            key=lambda item: (
                LESSON_TYPE_ORDER.get(item[0], LESSON_TYPE_ORDER["other"]),
                _compare_key(item[1]),
            ),
        ):
            lines.append(f"{teacher_lesson_type_label(lesson_type)} {teacher_name}")
        rendered_blocks.append("\n".join(lines))
    return rendered_blocks


def normalize_teacher_entries(entries: list[tuple[str, str]]) -> list[str]:
    normalized = normalize_teacher_records([(discipline, "other", teacher_name) for discipline, teacher_name in entries])
    return [f"{discipline}\n{teacher_name}" for discipline, _, teacher_name in normalized]
