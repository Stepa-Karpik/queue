from __future__ import annotations


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_compare_text(value: str) -> str:
    return normalize_name(value).replace("Ё", "Е").replace("ё", "е")


def normalize_group_name(value: str) -> str:
    return normalize_compare_text(value).upper()


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
