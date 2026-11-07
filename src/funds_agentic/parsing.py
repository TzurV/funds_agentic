"""Pure cell-based parsing. Missing cells keep their original periods."""
from __future__ import annotations
import math
import re

class ExtractionError(ValueError):
    """Source structure or a value cannot be interpreted safely."""

MISSING = {"", "-", "--", "\u2014", "\u2013", "n/a", "na", "n.a.", "not available"}

def clean(text: str) -> str:
    return " ".join(text.split())

def period(text: str) -> str | None:
    match = re.fullmatch(r"(1|3|5|6)\s*(m|y)(?:\s*\(%?\))?", clean(text).lower())
    return "".join(match.groups()) if match else None

def number(text: str) -> float | None:
    value = clean(text).lower().replace("\u2212", "-").removesuffix("%").strip()
    if value in MISSING:
        return None
    try:
        result = float(value.replace(",", ""))
    except ValueError as exc:
        raise ExtractionError(f"Unrecognized numeric cell: {text!r}") from exc
    if not math.isfinite(result):
        raise ExtractionError(f"Non-finite numeric cell: {text!r}")
    return result

def header_map(cells: list[str], required: tuple[str, ...]) -> dict[str, int]:
    positions = {}
    for index, cell in enumerate(cells):
        key = period(cell)
        if key in required:
            if key in positions:
                raise ExtractionError(f"Duplicate performance header: {key}")
            positions[key] = index
    if set(positions) != set(required):
        raise ExtractionError("Required performance headers are missing")
    return positions

def performance(cells: list[str], positions: dict[str, int]) -> dict[str, float | None]:
    if max(positions.values()) >= len(cells):
        raise ExtractionError("Performance row is shorter than its headers")
    return {key: number(cells[index]) for key, index in positions.items()}

def labeled_row(rows: list[list[str]], label: str) -> list[str] | None:
    matches = [row for row in rows if row and clean(row[0]).casefold().rstrip(":") == label.casefold().rstrip(":")]
    if len(matches) > 1:
        raise ExtractionError(f"Ambiguous table row: {label}")
    return matches[0] if matches else None

def ranking(value: str) -> int | None:
    text = clean(value)
    if text.lower() in MISSING:
        return None
    if not re.fullmatch(r"[1-4](?:st|nd|rd|th)?", text, re.I):
        raise ExtractionError(f"Invalid quartile: {value!r}")
    return int(text[0])
