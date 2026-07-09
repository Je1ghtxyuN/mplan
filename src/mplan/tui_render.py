from __future__ import annotations

from collections import defaultdict
from datetime import date

from mplan.month_grid import DayViewModel, build_month_grid
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

    return {
        "header": f"{state.visible_year}-{state.visible_month:02d} {state.mode}",
        "grid": grid,
        "layout": "compact" if width < (7 * 16 + 8) else "full",
        "footer": (
            f"{state.selected_day.isoformat()} {state.selected_bucket} "
            "方向键移动 Tab切换 i编辑 Esc保存 s同步 q退出"
        ),
        "editor_text": (
            state.edit_buffer
            if state.mode == "INSERT"
            else load_bucket_text(store, state.selected_day, state.selected_bucket)
        ),
    }
