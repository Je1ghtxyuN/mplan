from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DayCell:
    day: date
    imported_events: list[str]
    morning: list[str]
    afternoon: list[str]
    evening: list[str]
    in_month: bool
    selected: bool


def render_day_cell(cell: DayCell, width: int, height: int) -> list[str]:
    lines = [str(cell.day.day)]
    lines.append("正式:")
    lines.extend(cell.imported_events[:2] or [""])
    lines.append("早: " + " / ".join(cell.morning[:2]))
    lines.append("午: " + " / ".join(cell.afternoon[:2]))
    lines.append("晚: " + " / ".join(cell.evening[:2]))
    return [line[:width].ljust(width) for line in lines[:height]]
