import calendar
from dataclasses import dataclass
from datetime import date
import unicodedata


@dataclass(frozen=True)
class DayViewModel:
    imported_events: list[str]
    morning: list[str]
    afternoon: list[str]
    evening: list[str]


@dataclass(frozen=True)
class DayCell:
    day: date
    imported_events: list[str]
    morning: list[str]
    afternoon: list[str]
    evening: list[str]
    in_month: bool
    selected: bool
    selected_bucket: str | None = None


@dataclass(frozen=True)
class MonthGrid:
    year: int
    month: int
    weeks: list[list[DayCell]]


def build_month_grid(
    year: int,
    month: int,
    selected_day: date,
    day_data: dict[date, DayViewModel],
    selected_bucket: str = "早",
) -> MonthGrid:
    cal = calendar.Calendar(firstweekday=0)
    weeks: list[list[DayCell]] = []
    for week in cal.monthdatescalendar(year, month):
        rendered_week: list[DayCell] = []
        for day in week:
            model = day_data.get(
                day,
                DayViewModel(
                    imported_events=[],
                    morning=[],
                    afternoon=[],
                    evening=[],
                ),
            )
            rendered_week.append(
                DayCell(
                    day=day,
                    imported_events=model.imported_events,
                    morning=model.morning,
                    afternoon=model.afternoon,
                    evening=model.evening,
                    in_month=(day.month == month),
                    selected=(day == selected_day),
                    selected_bucket=selected_bucket if day == selected_day else None,
                )
            )
        weeks.append(rendered_week)
    return MonthGrid(year=year, month=month, weeks=weeks)


def render_day_cell(cell: DayCell, width: int, height: int) -> list[str]:
    inner_width = max(4, width)
    content_height = max(1, height)

    content_lines: list[str] = []
    day_label = f"[{cell.day.day}]" if cell.selected else str(cell.day.day)
    content_lines.append(day_label)
    if not cell.in_month:
        content_lines.append("(其他月)")

    content_lines.extend(_wrap_block("正式:", cell.imported_events, inner_width))
    content_lines.extend(
        _wrap_block("早:" if cell.selected_bucket != "早" else ">早:", cell.morning, inner_width)
    )
    content_lines.extend(
        _wrap_block("午:" if cell.selected_bucket != "午" else ">午:", cell.afternoon, inner_width)
    )
    content_lines.extend(
        _wrap_block("晚:" if cell.selected_bucket != "晚" else ">晚:", cell.evening, inner_width)
    )

    overflowed = len(content_lines) > content_height
    visible = content_lines[:content_height]
    if overflowed and content_height >= 2:
        visible = content_lines[: content_height - 1]
        visible.append("...")

    while len(visible) < content_height:
        visible.append("")

    return [_pad_display(line, inner_width) for line in visible]


def _wrap_block(label: str, items: list[str], width: int) -> list[str]:
    lines = [label]
    if not items:
        return lines
    for item in items:
        wrapped = _wrap_display_text(item, width=max(1, width - 2)) or [item]
        first, *rest = wrapped
        lines.append(f"  {first}")
        lines.extend(f"  {chunk}" for chunk in rest)
    return lines


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _trim_display(text: str, width: int) -> str:
    if width <= 0:
        return ""

    trimmed: list[str] = []
    used = 0
    for char in text:
        char_width = 0 if unicodedata.combining(char) else (
            2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
        )
        if used + char_width > width:
            break
        trimmed.append(char)
        used += char_width
    return "".join(trimmed)


def _pad_display(text: str, width: int) -> str:
    trimmed = _trim_display(text, width)
    padding = max(0, width - _display_width(trimmed))
    return trimmed + (" " * padding)


def _wrap_display_text(text: str, width: int) -> list[str]:
    if width <= 0:
        return [""]
    if not text:
        return [""]

    chunks: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and _display_width(candidate) > width:
            chunks.append(current)
            current = char
            if _display_width(current) > width:
                chunks.append(_trim_display(current, width))
                current = ""
            continue
        current = candidate
        if _display_width(current) > width:
            chunks.append(_trim_display(current, width))
            current = ""
    if current:
        chunks.append(current)
    return chunks or [""]
