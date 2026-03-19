from __future__ import annotations
import re


GROUP_NAME_EXAMPLES = "ВИ23, ВКБ21 или ВИАС33"
_GROUP_NAME_RE = re.compile(r"^[А-ЯЁ]+\d+$")


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_compare_text(value: str) -> str:
    return normalize_name(value).replace("Ё", "Е").replace("ё", "е")


def normalize_group_name(value: str) -> str:
    return normalize_compare_text(value).upper()


def normalize_valid_group_name(value: str) -> str | None:
    normalized = normalize_group_name(value)
    if not _GROUP_NAME_RE.fullmatch(normalized):
        return None
    return normalized


def get_group_validation_error_text() -> str:
    return f"Неверный формат. Верный: {GROUP_NAME_EXAMPLES}. Введите группу еще раз."


def normalize_faculty_name(value: str) -> str:
    normalized = normalize_compare_text(value).upper()
    compact = normalized.replace(" ", "")
    if compact in {"ИВТ", "ИИВТ"}:
        return "ИИВТ"
    return normalized


def split_full_name(value: str) -> tuple[str, str, str | None]:
    parts = normalize_name(value).split(" ")
    if len(parts) < 2:
        raise ValueError("ФИО должно содержать минимум фамилию и имя")
    last = parts[0]
    first = parts[1]
    middle = parts[2] if len(parts) > 2 else None
    return last, first, middle


def format_full_name(last: str, first: str, middle: str | None) -> str:
    if middle:
        return f"{last} {first} {middle}"
    return f"{last} {first}"


def format_short_name(last: str, first: str, middle: str | None) -> str:
    initials = [f"{first[0]}."]
    if middle:
        initials.append(f"{middle[0]}.")
    return f"{last} {' '.join(initials)}"
