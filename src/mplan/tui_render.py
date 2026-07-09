from __future__ import annotations

from collections import defaultdict
from datetime import date

from mplan.month_grid import DayCell, DayViewModel, build_month_grid
from mplan.tui_store import load_bucket_text


def build_screen_view(store, sync_engine, state, width: int, height: int) -> dict[str, object]:
    imported_by_day: dict[date, list[str]] = defaultdict(list)
    for event in sync_engine.pull_month(state.visible_year, state.visible_month):
        imported_by_day[event.starts_at.date()].append(
            f"{event.starts_at.strftime('%H:%M')} {event.title}"
        )

    items_by_day: dict[date, dict[str, list[str]]] = defaultdict(
        lambda: {"早": [], "午": [], "晚": []}
    )
    for day in store.list_days_in_month(state.visible_year, state.visible_month):
        for item in store.list_day_items(day):
            prefix = "✓ " if item.completed else ""
            items_by_day[day][item.bucket].append(prefix + item.text)

    day_data = {}
    for day, buckets in items_by_day.items():
        day_data[day] = DayViewModel(
            imported_events=imported_by_day.get(day, []),
            morning=buckets["早"],
            afternoon=buckets["午"],
            evening=buckets["晚"],
        )

    for day, imported in imported_by_day.items():
        if day not in day_data:
            day_data[day] = DayViewModel(
                imported_events=imported,
                morning=[],
                afternoon=[],
                evening=[],
            )

    grid = build_month_grid(
        state.visible_year,
        state.visible_month,
        selected_day=state.selected_day,
        day_data=day_data,
        selected_bucket=state.selected_bucket,
    )
    layout = "compact" if width < (7 * 16 + 8) else "full"

    return {
        "header": f"{state.visible_year}-{state.visible_month:02d} {state.mode}",
        "body": _build_body_lines(grid, layout, state.selected_day),
        "grid": grid,
        "layout": layout,
        "footer": _build_footer(store, state),
    }


def _build_body_lines(grid, layout: str, selected_day: date) -> list[str]:
    lines: list[str] = []
    for week in grid.weeks:
        if lines:
            lines.append("")
        if layout == "full":
            lines.append(_format_week(week))
        lines.extend(_build_visible_week_lines(week, selected_day))
    return lines


def _format_week(week: list[DayCell]) -> str:
    return " ".join(_format_day(cell) for cell in week)


def _format_day(cell: DayCell) -> str:
    day_text = f"{cell.day.day:02d}"
    if not cell.in_month:
        return f"({day_text})"
    if cell.selected:
        return f"[{day_text}]"
    return f" {day_text} "


def _build_selected_day_lines(cell: DayCell) -> list[str]:
    lines = [f"{cell.day.isoformat()} {cell.selected_bucket or '早'}"]
    lines.extend(_section_lines("正式", cell.imported_events))
    lines.extend(_section_lines("早", cell.morning))
    lines.extend(_section_lines("午", cell.afternoon))
    lines.extend(_section_lines("晚", cell.evening))
    return lines


def _section_lines(label: str, items: list[str]) -> list[str]:
    if not items:
        return [f"{label}: -"]
    return [f"{label}: {items[0]}", *(f"  {item}" for item in items[1:])]


def _build_visible_week_lines(week: list[DayCell], selected_day: date) -> list[str]:
    lines: list[str] = []
    for cell in week:
        if not cell.in_month:
            continue
        lines.extend(_build_day_lines(cell, selected_day))
    return lines


def _build_day_lines(cell: DayCell, selected_day: date) -> list[str]:
    marker = "*" if cell.day == selected_day else " "
    lines = [f"{marker} {cell.day.day:02d}"]
    if cell.imported_events:
        lines.append(f"  正式: {' ; '.join(cell.imported_events)}")
    if cell.morning:
        lines.append(f"  早: {' ; '.join(cell.morning)}")
    if cell.afternoon:
        lines.append(f"  午: {' ; '.join(cell.afternoon)}")
    if cell.evening:
        lines.append(f"  晚: {' ; '.join(cell.evening)}")
    return lines


def _build_footer(store, state) -> str:
    status_prefix = f"{state.status_message} " if state.status_message else ""

    if state.mode == "INSERT":
        return (
            f"{status_prefix}{state.selected_day.isoformat()} {state.selected_bucket} 编辑: "
            f"{state.edit_buffer} Esc保存"
        )

    current_text = load_bucket_text(store, state.selected_day, state.selected_bucket)
    if current_text:
        return (
            f"{status_prefix}{state.selected_day.isoformat()} {state.selected_bucket} {current_text} "
            "方向键移动 Tab切换 i编辑 s同步 q退出"
        )
    return (
        f"{status_prefix}{state.selected_day.isoformat()} {state.selected_bucket} "
        "方向键移动 Tab切换 i编辑 s同步 q退出"
    )
