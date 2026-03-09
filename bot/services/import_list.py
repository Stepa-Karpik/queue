from __future__ import annotations

from io import BytesIO

import openpyxl

from bot.utils.names import split_full_name


def parse_text_list(content: str) -> list[tuple[str, str, str | None]]:
    students: list[tuple[str, str, str | None]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last, first, middle = split_full_name(line)
        except ValueError:
            continue
        students.append((last, first, middle))
    return students


def parse_excel(data: bytes) -> list[tuple[str, str, str | None]]:
    wb = openpyxl.load_workbook(BytesIO(data))
    sheet = wb.active
    students: list[tuple[str, str, str | None]] = []
    for row in sheet.iter_rows(values_only=True):
        if not row:
            continue
        # Expect either full name in first cell or 3 columns
        if row[0] and isinstance(row[0], str):
            try:
                last, first, middle = split_full_name(str(row[0]))
                students.append((last, first, middle))
                continue
            except ValueError:
                pass
        if len(row) >= 2 and row[0] and row[1]:
            last = str(row[0]).strip()
            first = str(row[1]).strip()
            middle = str(row[2]).strip() if len(row) > 2 and row[2] else None
            if last and first:
                students.append((last, first, middle))
    return students
