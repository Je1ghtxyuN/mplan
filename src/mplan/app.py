from __future__ import annotations

from contextlib import redirect_stdout
from collections import defaultdict, deque
from datetime import date
from datetime import timedelta
from io import StringIO
import os
import select
import shutil
import sys
import termios
import threading
import time
import tty

from mplan.day_editor import edit_day
from mplan.detail_view import build_detail_view
from mplan.grid_edit import (
    build_statusline,
    colorize_mode_label,
    create_bucket_task,
    cycle_bucket,
    load_bucket_items,
    parse_command,
)
from mplan.models import PlannerBucket
from mplan.month_grid import DayViewModel, build_month_grid, render_day_cell

_PENDING_KEY_BYTES = ""
_PENDING_KEY_DEADLINE = 0.0
_ESC_SEQUENCE_TIMEOUT_NORMAL = 0.35
_ESC_SEQUENCE_TIMEOUT_INSERT = 0.08
_PENDING_INPUT_CHARS: deque[str] = deque()
_PENDING_INPUT_BYTES = bytearray()


def run_app(store, sync_engine) -> int:
    today = date.today()
    state = {
        "current": today.replace(day=1),
        "selected": today,
        "bucket": "早",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "detail_task_index": 0,
        "edit_item": None,
        "status": "",
    }
    while True:
        _render_app(store, sync_engine, state)
        command = _read_key(state["mode"])
        if not command:
            continue
        if state["mode"] == "COMMAND":
            state = _handle_command_key(
                state,
                command,
                command_func=lambda name: _execute_tui_command(
                    state,
                    name,
                    store,
                    sync_engine,
                    lambda day: edit_day(store, day),
                ),
            )
            if state.get("quit"):
                return 0
            continue
        if state["mode"] == "INSERT":
            state = _handle_insert_key(
                state,
                command,
                save_func=lambda day, bucket, raw, existing: _save_task(
                    store, day, bucket, raw, existing
                ),
            )
            continue
        if state.get("detail_open"):
            detail_items = _load_detail_items(store, state["selected"])
            state = _handle_detail_command(
                state,
                command,
                detail_items,
                toggle_func=lambda item: store.set_completed(item.id, not item.completed),
                delete_func=lambda item: _delete_task(store, sync_engine, item),
            )
            continue
        state = _handle_normal_command(
            state,
            command,
            load_buffer_func=lambda day, bucket: "",
        )
        if state.get("quit"):
            return 0


def _render_app(store, sync_engine, state: dict[str, object]) -> None:
    current = state["current"]
    selected = state["selected"]
    bucket = state["bucket"]
    mode = state["mode"]
    buffer = state["command_buffer"] if mode == "COMMAND" else state["buffer"]
    status = state["status"]
    detail_open = state.get("detail_open", False)
    month_rows = _collect_month_rows(
        store,
        sync_engine,
        current.year,
        current.month,
        selected,
        selected_bucket=bucket,
    )
    total_lines = shutil.get_terminal_size((180, 40)).lines
    visible_rows = _fit_grid_rows_for_statusline(month_rows, total_lines=total_lines)
    if detail_open:
        visible_rows = _render_detail_overlay(
            store,
            sync_engine,
            selected,
            bucket,
            state.get("detail_task_index"),
            visible_rows,
        )
        if not status:
            status = "Tab切分区 ↑↓选择 i新增 e编辑 Space完成/取消 d删除 Esc关闭"
    statusline = build_statusline(mode, selected, bucket, status, buffer=buffer)
    statusline = statusline.replace(mode, colorize_mode_label(mode), 1)

    print("\033[2J\033[H", end="")
    if visible_rows:
        print("\n".join(visible_rows))
    print(statusline)


def _handle_normal_command(
    state: dict[str, object],
    command: str,
    load_buffer_func=None,
) -> dict[str, object]:
    if command == ":":
        return _enter_command_mode(state)
    if command == "ENTER":
        return _open_detail_view(state)
    if command == "ESC" and state.get("detail_open"):
        return _close_detail_view(state)
    if command == "\t":
        return {**state, "bucket": cycle_bucket(state["bucket"]), "status": ""}
    if command == "i":
        return {
            **state,
            "mode": "INSERT",
            "buffer": load_buffer_func(state["selected"], state["bucket"]) if load_buffer_func else "",
            "status": "新建任务",
        }
    if command == "LEFT":
        return _move_selection(state, -1)
    if command == "RIGHT":
        return _move_selection(state, 1)
    if command == "UP":
        return _move_selection(state, -7)
    if command == "DOWN":
        return _move_selection(state, 7)
    if command in {"q", "s", "v", "e", "n", "p"}:
        return {**state, "status": "NORMAL仅选择 用:执行命令"}
    return {**state, "status": "方向键移动 Tab切分区 i新增 Enter详情 :命令"}


def _enter_command_mode(state: dict[str, object]) -> dict[str, object]:
    return {**state, "mode": "COMMAND", "command_buffer": ":", "status": ""}


def _open_detail_view(state: dict[str, object]) -> dict[str, object]:
    return {**state, "detail_open": True, "detail_task_index": 0, "status": ""}


def _close_detail_view(state: dict[str, object]) -> dict[str, object]:
    return {**state, "detail_open": False, "detail_task_index": 0, "status": ""}


def _load_detail_items(store, day: date) -> list:
    return [
        item
        for bucket in ("早", "午", "晚")
        for item in store.list_bucket_items(day, bucket)
    ]


def _handle_detail_command(
    state: dict[str, object],
    key: str,
    items: list,
    toggle_func,
    delete_func,
) -> dict[str, object]:
    if key == "ESC":
        return _close_detail_view(state)

    bucket = state.get("bucket")
    bucket_indices = [
        index
        for index, item in enumerate(items)
        if bucket is None or getattr(item, "bucket", bucket) == bucket
    ]
    if key == "\t":
        next_bucket = cycle_bucket(bucket or "早")
        next_indices = [
            index
            for index, item in enumerate(items)
            if getattr(item, "bucket", next_bucket) == next_bucket
        ]
        return {
            **state,
            "bucket": next_bucket,
            "detail_task_index": next_indices[0] if next_indices else None,
            "status": "",
        }
    if key == "i":
        return {
            **state,
            "mode": "INSERT",
            "buffer": "",
            "edit_item": None,
            "status": "新建任务",
        }
    if key == "e" and not bucket_indices:
        return {
            **state,
            "detail_task_index": None,
            "status": "当前分区没有可编辑任务",
        }
    if not items:
        return {**state, "detail_task_index": 0, "status": "没有可操作的本地任务"}

    if not bucket_indices:
        return {
            **state,
            "detail_task_index": None,
            "status": "当前分区没有本地任务，按i新增",
        }

    current_index = state.get("detail_task_index")
    index = current_index if current_index in bucket_indices else bucket_indices[0]
    bucket_position = bucket_indices.index(index)
    if key == "UP":
        return {
            **state,
            "detail_task_index": bucket_indices[max(0, bucket_position - 1)],
            "status": "",
        }
    if key == "DOWN":
        return {
            **state,
            "detail_task_index": bucket_indices[
                min(len(bucket_indices) - 1, bucket_position + 1)
            ],
            "status": "",
        }
    if key == "e":
        item = items[index]
        return {
            **state,
            "mode": "INSERT",
            "bucket": item.bucket,
            "buffer": item.text,
            "edit_item": item,
            "status": "编辑任务",
        }
    if key == " ":
        item = items[index]
        try:
            toggle_func(item)
        except Exception as exc:
            return {**state, "detail_task_index": index, "status": f"更新失败: {exc}"}
        return {
            **state,
            "detail_task_index": index,
            "status": "已取消完成" if item.completed else "已完成",
        }
    if key == "d":
        try:
            delete_func(items[index])
        except Exception as exc:
            return {**state, "detail_task_index": index, "status": f"删除失败: {exc}"}
        return {
            **state,
            "detail_task_index": min(index, max(0, len(items) - 2)),
            "status": "已删除",
        }
    return {
        **state,
        "detail_task_index": index,
        "status": "Tab切分区 ↑↓选择 i新增 e编辑 Space完成/取消 d删除 Esc关闭",
    }


def _delete_task(store, sync_engine, item) -> None:
    if item.external_event_id:
        sync_engine.bridge.delete_owned_event(item.external_event_id)
    store.delete_planner_item(item.id)


def _handle_command_key(
    state: dict[str, object],
    key: str,
    command_func,
) -> dict[str, object]:
    if key == "ESC":
        return {**state, "mode": "NORMAL", "command_buffer": ""}
    if key == "BACKSPACE":
        buffer = state["command_buffer"][:-1]
        return {**state, "command_buffer": buffer or ":"}
    if key == "ENTER":
        result = command_func(parse_command(state["command_buffer"]))
        return {**state, **result, "mode": "NORMAL", "command_buffer": ""}
    if len(key) == 1 and key.isprintable():
        return {**state, "command_buffer": f"{state['command_buffer']}{key}"}
    return state


def _handle_insert_key(
    state: dict[str, object],
    key: str,
    save_func,
) -> dict[str, object]:
    if key == "ESC":
        existing = state.get("edit_item")
        save_func(state["selected"], state["bucket"], state["buffer"], existing)
        return {
            **state,
            "mode": "NORMAL",
            "edit_item": None,
            "status": "已更新" if existing else "已保存",
        }
    if key == "ENTER":
        return state
    if key == "BACKSPACE":
        return {**state, "buffer": state["buffer"][:-1]}
    if key in {"UP", "DOWN", "LEFT", "RIGHT", "\t"}:
        return state
    if len(key) == 1 and key.isprintable():
        return {**state, "buffer": f"{state['buffer']}{key}"}
    return state


def _move_selection(state: dict[str, object], delta_days: int) -> dict[str, object]:
    selected = state["selected"] + timedelta(days=delta_days)
    return {
        **state,
        "selected": selected,
        "current": selected.replace(day=1),
        "status": "",
    }


def _fit_grid_rows_for_statusline(rows: list[str], total_lines: int) -> list[str]:
    available = max(0, total_lines - 1)
    return rows[:available]


def _render_detail_overlay(
    store,
    sync_engine,
    selected_day: date,
    bucket: PlannerBucket,
    detail_task_index,
    month_rows: list[str],
) -> list[str]:
    size = shutil.get_terminal_size((180, 40))
    bucket_items = {
        name: load_bucket_items(store, selected_day, name)
        for name in ("早", "午", "晚")
    }
    imported_events = [
        event
        for event in sync_engine.cached_month(selected_day.year, selected_day.month)
        if event.starts_at.date() == selected_day
    ]
    overlay_rows = build_detail_view(
        selected_day,
        bucket,
        imported_events,
        bucket_items,
        detail_task_index,
        size.columns,
        max(0, size.lines - 1),
    )
    return overlay_rows


def _save_task(store, day: date, bucket: PlannerBucket, raw: str, existing=None) -> None:
    text = raw.strip()
    if not text:
        return
    if existing is not None:
        store.update_planner_item(existing.with_text(text))
        return
    create_bucket_task(store, day, bucket, text)


def _execute_command(state, command: str, sync_engine, edit_func) -> dict[str, object]:
    if command == "quit":
        return {"quit": True}
    if command == "sync":
        current = state["current"]
        try:
            report = sync_engine.sync_month(current.year, current.month)
        except Exception as exc:
            return {"status": f"同步失败: {exc}"}
        return {"status": _format_sync_report(report)}
    if command == "syncquit":
        result = _execute_command(state, "sync", sync_engine, edit_func)
        if result.get("status", "").startswith("同步失败"):
            return result
        return {**result, "quit": True}
    if command == "view":
        return _open_detail_view(state)
    if command == "next":
        current = _shift_month(state["current"], 1)
        return {"current": current, "selected": current, "status": ""}
    if command == "prev":
        current = _shift_month(state["current"], -1)
        return {"current": current, "selected": current, "status": ""}
    if command == "edit":
        edit_func(state["selected"])
        return {"status": "已打开编辑器"}
    return {"status": f"未知命令: {command}"}


def _execute_tui_command(state, command: str, store, sync_engine, edit_func):
    if command in {"sync", "syncquit"}:
        return _run_sync_with_spinner(
            state,
            sync_engine,
            lambda progress_state: _render_app(store, sync_engine, progress_state),
            quit_after_success=(command == "syncquit"),
        )
    return _execute_command(state, command, sync_engine, edit_func)


def _run_sync_with_spinner(
    state,
    sync_engine,
    render_func,
    *,
    quit_after_success: bool = False,
    frame_interval: float = 0.1,
) -> dict[str, object]:
    frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    finished = threading.Event()
    outcome: dict[str, object] = {}
    current = state["current"]

    def sync_worker() -> None:
        try:
            outcome["report"] = sync_engine.sync_month(current.year, current.month)
        except Exception as exc:
            outcome["error"] = exc
        finally:
            finished.set()

    def render_frame(frame: str) -> None:
        render_func(
            {
                **state,
                "mode": "NORMAL",
                "command_buffer": "",
                "status": f"{frame} 正在同步…",
            }
        )

    render_frame(frames[0])
    worker = threading.Thread(target=sync_worker, name="mplan-sync", daemon=True)
    worker.start()
    frame_index = 1
    while not finished.wait(frame_interval):
        render_frame(frames[frame_index % len(frames)])
        frame_index += 1
    worker.join()

    if "error" in outcome:
        return {"status": f"同步失败: {outcome['error']}"}
    result: dict[str, object] = {
        "status": _format_sync_report(outcome["report"]),
    }
    if quit_after_success:
        result["quit"] = True
    return result


def _format_sync_report(report) -> str:
    status = (
        f"已同步 导入{report.imported_count} 导出{report.exported_count} "
        f"更新{report.updated_count}"
    )
    if getattr(report, "warning", None):
        status = f"{status} {report.warning}"
    return status


def _collect_month_rows(
    store,
    sync_engine,
    year: int,
    month: int,
    selected_day: date,
    selected_bucket: PlannerBucket = "早",
) -> list[str]:
    buffer = StringIO()
    with redirect_stdout(buffer):
        _print_month(
            store,
            sync_engine,
            year,
            month,
            selected_day,
            selected_bucket=selected_bucket,
        )
    return buffer.getvalue().splitlines()


def _read_key(mode: str = "NORMAL") -> str:
    if not sys.stdin.isatty():
        return input().strip()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        first = _read_fd_char(fd)
        if first == "\x1b":
            sequence = ""
            timeout_window = (
                _ESC_SEQUENCE_TIMEOUT_INSERT
                if mode == "INSERT"
                else _ESC_SEQUENCE_TIMEOUT_NORMAL
            )
            deadline = time.monotonic() + timeout_window
            while time.monotonic() < deadline:
                timeout = max(0.0, deadline - time.monotonic())
                if not _PENDING_INPUT_CHARS and not select.select(
                    [sys.stdin], [], [], timeout
                )[0]:
                    break
                sequence += _read_fd_char(fd)
                if sequence[-1] == "~":
                    break
                if len(sequence) > 1 and sequence[-1].isalpha():
                    break
            return _decode_escape_sequence(sequence)
        if first in {"\r", "\n"}:
            return "ENTER"
        if first == "\x7f":
            return "BACKSPACE"
        return first
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_fd_char(fd: int) -> str:
    if _PENDING_INPUT_CHARS:
        return _PENDING_INPUT_CHARS.popleft()

    while not _PENDING_INPUT_CHARS:
        chunk = os.read(fd, 64)
        if not chunk:
            return ""
        _PENDING_INPUT_BYTES.extend(chunk)
        try:
            decoded = bytes(_PENDING_INPUT_BYTES).decode("utf-8")
        except UnicodeDecodeError as exc:
            if exc.reason == "unexpected end of data":
                continue
            decoded = bytes(_PENDING_INPUT_BYTES).decode("utf-8", errors="replace")
        _PENDING_INPUT_BYTES.clear()
        _PENDING_INPUT_CHARS.extend(decoded)
    return _PENDING_INPUT_CHARS.popleft()


def _decode_escape_sequence(sequence: str) -> str:
    if not sequence:
        return "ESC"

    final = sequence[-1]
    return {
        "A": "UP",
        "B": "DOWN",
        "C": "RIGHT",
        "D": "LEFT",
    }.get(final, "ESC")


def _consume_pending_key(first: str) -> str | None:
    global _PENDING_KEY_BYTES
    global _PENDING_KEY_DEADLINE

    if not _PENDING_KEY_BYTES:
        return None
    if time.monotonic() >= _PENDING_KEY_DEADLINE:
        _clear_pending_key()
        return None

    sequence = _PENDING_KEY_BYTES + first
    if sequence in {"\x1b[", "\x1bO"}:
        _PENDING_KEY_BYTES = sequence
        return ""
    if sequence.startswith(("\x1b[", "\x1bO")):
        _clear_pending_key()
        return _decode_escape_sequence(sequence[1:])

    _clear_pending_key()
    return None


def _clear_pending_key() -> None:
    global _PENDING_KEY_BYTES
    global _PENDING_KEY_DEADLINE

    _PENDING_KEY_BYTES = ""
    _PENDING_KEY_DEADLINE = 0.0


def _print_month(
    store,
    sync_engine,
    year: int,
    month: int,
    selected_day: date,
    selected_bucket: PlannerBucket = "早",
) -> None:
    imported_by_day: dict[date, list[str]] = defaultdict(list)
    for event in sync_engine.cached_month(year, month):
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

    grid = build_month_grid(
        year,
        month,
        selected_day=selected_day,
        day_data=day_data,
        selected_bucket=selected_bucket,
    )
    columns = shutil.get_terminal_size((180, 40)).columns
    min_grid_columns = 7 * 16 + 8
    if columns < min_grid_columns:
        _print_month_compact(grid)
        return

    cell_width = max(16, min(24, (columns - 8) // 7))
    cell_height = 8
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    border = "+" + "+".join("-" * cell_width for _ in range(7)) + "+"
    print(f"\n{year}-{month:02d}")
    print(" " + " ".join(name.center(cell_width) for name in weekday_names))
    print(border)
    for week in grid.weeks:
        rendered = [render_day_cell(cell, width=cell_width, height=cell_height) for cell in week]
        for row in range(cell_height):
            print("|" + "|".join(cell[row] for cell in rendered) + "|")
        print(border)


def _print_month_compact(grid) -> None:
    print(f"\n{grid.year}-{grid.month:02d} (紧凑视图)")
    for week in grid.weeks:
        print("-" * 32)
        for cell in week:
            if not cell.in_month:
                continue
            marker = "*" if cell.selected else " "
            print(f"{marker} {cell.day.day:02d}")
            if cell.imported_events:
                print(f"  正式: {' ; '.join(cell.imported_events)}")
            if cell.morning:
                print(f"  早: {' ; '.join(cell.morning)}")
            if cell.afternoon:
                print(f"  午: {' ; '.join(cell.afternoon)}")
            if cell.evening:
                print(f"  晚: {' ; '.join(cell.evening)}")
    print("-" * 32)


def _print_day_details(store, sync_engine, day: date) -> None:
    print(f"\n{day.isoformat()} 完整内容")
    imported = [
        event
        for event in sync_engine.cached_month(day.year, day.month)
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
