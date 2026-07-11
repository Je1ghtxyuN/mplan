from dataclasses import dataclass
from datetime import date

from mplan.models import ImportedCalendarEvent, PlannerItem


@dataclass(frozen=True)
class DetailViewModel:
    day: date
    bucket: str
    width: int
    height: int
    rows: list[str]


def _fit_line(text: str, inner_width: int) -> str:
    return text[:inner_width].ljust(inner_width)


def build_detail_view(
    day: date,
    bucket: str,
    imported_events: list[ImportedCalendarEvent],
    bucket_items: dict[str, list[PlannerItem]],
    selected_task_index: int | None,
    width: int,
    height: int,
) -> list[str]:
    del selected_task_index

    panel_width = max(24, min(width - 4, 56))
    panel_height = max(10, min(height - 2, 14))
    inner_width = panel_width - 4

    panel_rows = [
        f"╔{'═' * (panel_width - 2)}╗",
        f"║ {_fit_line(day.isoformat(), inner_width)} ║",
        f"║ {_fit_line('正式日程', inner_width)} ║",
    ]
    for event in imported_events:
        event_line = f"{event.starts_at.strftime('%H:%M')} {event.title}"
        panel_rows.append(f"║ {_fit_line(event_line, inner_width)} ║")

    for section in ("早", "午", "晚"):
        marker = ">" if section == bucket else " "
        panel_rows.append(f"║ {_fit_line(f'{marker} {section}', inner_width)} ║")
        for item in bucket_items.get(section, []):
            panel_rows.append(f"║ {_fit_line(f'  {item.text}', inner_width)} ║")

    panel_rows = panel_rows[: panel_height - 1]
    while len(panel_rows) < panel_height - 1:
        panel_rows.append(f"║ {' ' * inner_width} ║")
    panel_rows.append(f"╚{'═' * (panel_width - 2)}╝")

    left_pad = max(0, (width - panel_width) // 2)
    centered_panel = [(" " * left_pad) + row for row in panel_rows]
    full_rows: list[str] = []
    top_pad = max(0, (height - panel_height) // 2)

    for _ in range(top_pad):
        full_rows.append(" " * width)
    for row in centered_panel:
        full_rows.append(row.ljust(width))
    while len(full_rows) < height:
        full_rows.append(" " * width)
    return full_rows[:height]
