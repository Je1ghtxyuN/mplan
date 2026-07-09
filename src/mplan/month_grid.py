import calendar
from dataclasses import dataclass
from datetime import date
from textwrap import wrap


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
    inner_width = max(4, width - 2)
    content_height = max(1, height - 2)

    content_lines: list[str] = []
    day_label = f"[{cell.day.day}]" if cell.selected else str(cell.day.day)
    content_lines.append(day_label)
    if not cell.in_month:
        content_lines.append("(其他月)")

    content_lines.extend(_wrap_block("正式:", cell.imported_events, inner_width))
    content_lines.extend(_wrap_block("早:", cell.morning, inner_width))
    content_lines.extend(_wrap_block("午:", cell.afternoon, inner_width))
    content_lines.extend(_wrap_block("晚:", cell.evening, inner_width))

    overflowed = len(content_lines) > content_height
    visible = content_lines[:content_height]
    if overflowed and content_height >= 2:
        visible = content_lines[: content_height - 1]
        visible.append(f"... v {cell.day.day}")

    while len(visible) < content_height:
        visible.append("")

    boxed = ["+" + "-" * inner_width + "+"]
    boxed.extend("|" + line[:inner_width].ljust(inner_width) + "|" for line in visible)
    boxed.append("+" + "-" * inner_width + "+")
    return boxed


def _wrap_block(label: str, items: list[str], width: int) -> list[str]:
    lines = [label]
    if not items:
        return lines
    for item in items:
        wrapped = wrap(
            item,
            width=max(1, width - 2),
            break_long_words=True,
            break_on_hyphens=False,
        ) or [item]
        first, *rest = wrapped
        lines.append(f"  {first}")
        lines.extend(f"  {chunk}" for chunk in rest)
    return lines
