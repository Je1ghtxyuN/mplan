from dataclasses import dataclass
from datetime import date
import unicodedata

from mplan.models import ImportedCalendarEvent, PlannerItem


@dataclass(frozen=True)
class DetailViewModel:
    day: date
    bucket: str
    width: int
    height: int
    rows: list[str]


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return width


def _trim_display(text: str, width: int) -> str:
    result: list[str] = []
    used = 0
    for char in text:
        char_width = 0 if unicodedata.combining(char) else (
            2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
        )
        if used + char_width > width:
            break
        result.append(char)
        used += char_width
    return "".join(result)


def _fit_line(text: str, inner_width: int) -> str:
    fitted = _trim_display(text, inner_width)
    return fitted + (" " * max(0, inner_width - _display_width(fitted)))


def _flatten_bucket_items(bucket_items: dict[str, list[PlannerItem]]) -> list[PlannerItem]:
    return [item for section in ("早", "午", "晚") for item in bucket_items.get(section, [])]


def build_detail_view(
    day: date,
    bucket: str,
    imported_events: list[ImportedCalendarEvent],
    bucket_items: dict[str, list[PlannerItem]],
    selected_task_index: int | None,
    width: int,
    height: int,
) -> list[str]:
    if width < 4 or height < 3:
        return [_fit_line(day.isoformat(), max(0, width)) for _ in range(max(0, height))]

    panel_width = min(56, width)
    panel_height = min(14, height)
    inner_width = panel_width - 4

    content_rows: list[tuple[str, bool]] = [
        (day.isoformat(), False),
        ("正式日程", False),
    ]
    for event in imported_events:
        event_line = f"{event.starts_at.strftime('%H:%M')} {event.title}"
        content_rows.append((event_line, False))

    all_items = _flatten_bucket_items(bucket_items)
    selected_id = None
    if all_items and selected_task_index is not None:
        selected_id = all_items[max(0, min(selected_task_index, len(all_items) - 1))].id

    for section in ("早", "午", "晚"):
        marker = ">" if section == bucket else " "
        content_rows.append((f"{marker} {section}", False))
        for item in bucket_items.get(section, []):
            cursor = ">" if item.id == selected_id else " "
            completed = "✓ " if item.completed else ""
            content_rows.append((f"{cursor} {completed}{item.text}", item.id == selected_id))

    content_height = panel_height - 2
    selected_row = next(
        (index for index, (_, selected) in enumerate(content_rows) if selected),
        0,
    )
    start = max(0, selected_row - content_height + 1)
    start = min(start, max(0, len(content_rows) - content_height))
    visible_content = content_rows[start : start + content_height]

    panel_rows = [f"╔{'═' * (panel_width - 2)}╗"]
    panel_rows.extend(
        f"║ {_fit_line(text, inner_width)} ║" for text, _ in visible_content
    )
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
        full_rows.append(_fit_line(row, width))
    while len(full_rows) < height:
        full_rows.append(" " * width)
    return full_rows[:height]
