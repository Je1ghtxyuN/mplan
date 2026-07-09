import calendar
from dataclasses import dataclass
from datetime import date


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
                )
            )
        weeks.append(rendered_week)
    return MonthGrid(year=year, month=month, weeks=weeks)


def render_day_cell(cell: DayCell, width: int, height: int) -> list[str]:
    day_label = str(cell.day.day)
    if cell.selected:
        day_label = f"[{day_label}]"
    lines = [day_label]
    if not cell.in_month:
        lines.append("(其他月)")
    lines.append("正式:")
    lines.extend(cell.imported_events[:2] or [""])
    lines.append("早: " + " / ".join(cell.morning[:2]))
    lines.append("午: " + " / ".join(cell.afternoon[:2]))
    lines.append("晚: " + " / ".join(cell.evening[:2]))
    return [line[:width].ljust(width) for line in lines[:height]]
