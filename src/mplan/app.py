from __future__ import annotations

from collections import defaultdict
from datetime import date
import shutil

from mplan.day_editor import edit_day
from mplan.month_grid import DayViewModel, build_month_grid, render_day_cell


def run_app(store, sync_engine) -> int:
    current = date.today().replace(day=1)
    selected = date.today()
    while True:
        _print_month(store, sync_engine, current.year, current.month, selected)
        command = input(
            "\n命令: [n]下月 [p]上月 [e DD]编辑 [v DD]查看 [s]同步 [q]退出 > "
        ).strip()
        if command == "q":
            return 0
        if command == "n":
            current = _shift_month(current, 1)
            selected = current
            continue
        if command == "p":
            current = _shift_month(current, -1)
            selected = current
            continue
        if command == "s":
            report = sync_engine.sync_month(current.year, current.month)
            print(
                f"已同步: 导入 {report.imported_count}，导出 {report.exported_count}，更新 {report.updated_count}"
            )
            continue
        if command.startswith("e"):
            parts = command.split()
            if len(parts) == 2 and parts[1].isdigit():
                try:
                    selected = date(current.year, current.month, int(parts[1]))
                    edit_day(store, selected)
                except ValueError:
                    print("日期无效")
            else:
                print("用法: e 12")
            continue
        if command.startswith("v"):
            parts = command.split()
            if len(parts) == 2 and parts[1].isdigit():
                try:
                    selected = date(current.year, current.month, int(parts[1]))
                    _print_day_details(store, sync_engine, selected)
                except ValueError:
                    print("日期无效")
            else:
                print("用法: v 12")
            continue
        print("未知命令")


def _print_month(store, sync_engine, year: int, month: int, selected_day: date) -> None:
    imported_by_day: dict[date, list[str]] = defaultdict(list)
    for event in sync_engine.pull_month(year, month):
        imported_by_day[event.starts_at.date()].append(
            f"{event.starts_at.strftime('%H:%M')} {event.title}"
        )

    items_by_day: dict[date, dict[str, list[str]]] = defaultdict(
        lambda: {"早": [], "午": [], "晚": []}
    )
    for day in store.list_days_in_month(year, month):
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

    grid = build_month_grid(year, month, selected_day=selected_day, day_data=day_data)
    columns = shutil.get_terminal_size((180, 40)).columns
    cell_width = max(18, min(28, columns // 7 - 1))
    cell_height = 10
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    print(f"\n{year}-{month:02d}")
    print("".join(name.center(cell_width) for name in weekday_names))
    for week in grid.weeks:
        rendered = [render_day_cell(cell, width=cell_width, height=cell_height) for cell in week]
        for row in range(cell_height):
            print("".join(cell[row] for cell in rendered))


def _print_day_details(store, sync_engine, day: date) -> None:
    print(f"\n{day.isoformat()} 完整内容")
    imported = [
        event
        for event in sync_engine.pull_month(day.year, day.month)
        if event.starts_at.date() == day
    ]
    print("正式日程:")
    if imported:
        for event in imported:
            print(f"  - {event.starts_at.strftime('%H:%M')} {event.title}")
    else:
        print("  (空)")

    items = store.list_day_items(day)
    for bucket in ("早", "午", "晚"):
        print(f"{bucket}:")
        bucket_items = [item for item in items if item.bucket == bucket]
        if bucket_items:
            for idx, item in enumerate(bucket_items, start=1):
                prefix = "✓ " if item.completed else ""
                print(f"  {idx}. {prefix}{item.text}")
        else:
            print("  (空)")


def _shift_month(current: date, delta: int) -> date:
    month = current.month + delta
    year = current.year
    while month < 1:
        year -= 1
        month += 12
    while month > 12:
        year += 1
        month -= 12
    return date(year, month, 1)
