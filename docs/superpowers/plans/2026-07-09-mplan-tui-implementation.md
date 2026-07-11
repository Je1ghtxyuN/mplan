# mplan TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the prompt-driven month app with a Vim-like full-screen terminal UI that supports day and bucket navigation, footer-based insert editing, local save-on-escape, and explicit month sync.

**Architecture:** Add a dedicated TUI layer split into state, rendering, and runtime modules. Keep SQLite storage, planner models, and Calendar sync in place, route the default interactive entrypoint through the new TUI, and cover the new behavior with pure-logic tests before wiring curses I/O.

**Tech Stack:** Python 3.13, `curses`, `pytest`, existing `mplan` storage/sync/month-grid modules

## Global Constraints

- Keep the selection unit as `day + bucket` where bucket is exactly one of `早`, `午`, or `晚`.
- Keep only two modes in v1: `NORMAL` and `INSERT`.
- Save locally on `Esc` from `INSERT`; do not auto-sync on edit exit.
- Sync only on `s` in `NORMAL`.
- Reuse the existing SQLite schema; do not add migrations.
- Keep CLI subcommands `add`, `done`, `sync`, and `doctor` working unchanged.
- Preserve current month-grid semantics for imported events and planner buckets.
- Put the active edit surface in the footer, not inline inside the day cell.
- Prefer pure functions for navigation, serialization, and render-model generation so tests do not require a live terminal.

---

### Task 1: Add TUI state primitives and bucket serialization helpers

**Files:**
- Create: `src/mplan/tui_state.py`
- Test: `tests/test_tui_state.py`

**Interfaces:**
- Consumes: `mplan.models.PlannerBucket`
- Produces: `EditorMode`, `TuiState`, `cycle_bucket(bucket: str, reverse: bool = False) -> str`, `enter_insert_mode(state: TuiState, initial_text: str) -> TuiState`, `exit_insert_mode(state: TuiState, status_message: str = "") -> TuiState`, `serialize_bucket_text(items: list[str]) -> str`, `parse_bucket_text(raw: str) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.tui_state import (
    TuiState,
    cycle_bucket,
    enter_insert_mode,
    exit_insert_mode,
    parse_bucket_text,
    serialize_bucket_text,
)


def test_cycle_bucket_wraps_forward_and_backward():
    assert cycle_bucket("早") == "午"
    assert cycle_bucket("晚") == "早"
    assert cycle_bucket("早", reverse=True) == "晚"


def test_enter_insert_mode_sets_mode_and_buffer():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    updated = enter_insert_mode(state, "看论文 | 回消息")
    assert updated.mode == "INSERT"
    assert updated.edit_buffer == "看论文 | 回消息"


def test_exit_insert_mode_clears_buffer_and_sets_status():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    editing = enter_insert_mode(state, "看论文")
    updated = exit_insert_mode(editing, "已保存")
    assert updated.mode == "NORMAL"
    assert updated.edit_buffer == ""
    assert updated.status_message == "已保存"


def test_bucket_text_round_trip_trims_and_drops_empty_segments():
    assert parse_bucket_text(" 看论文 |  | 回消息 | ") == ["看论文", "回消息"]
    assert serialize_bucket_text(["看论文", "回消息"]) == "看论文 | 回消息"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_state.py -v`
Expected: FAIL with `ModuleNotFoundError` for `mplan.tui_state`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from mplan.models import PlannerBucket

EditorMode = Literal["NORMAL", "INSERT"]
BUCKET_ORDER: tuple[PlannerBucket, ...] = ("早", "午", "晚")


@dataclass(frozen=True)
class TuiState:
    visible_year: int
    visible_month: int
    selected_day: date
    selected_bucket: PlannerBucket
    mode: EditorMode
    edit_buffer: str
    status_message: str

    @classmethod
    def initial(cls, selected_day: date) -> "TuiState":
        return cls(
            visible_year=selected_day.year,
            visible_month=selected_day.month,
            selected_day=selected_day,
            selected_bucket="早",
            mode="NORMAL",
            edit_buffer="",
            status_message="",
        )


def cycle_bucket(bucket: PlannerBucket, reverse: bool = False) -> PlannerBucket:
    index = BUCKET_ORDER.index(bucket)
    delta = -1 if reverse else 1
    return BUCKET_ORDER[(index + delta) % len(BUCKET_ORDER)]


def enter_insert_mode(state: TuiState, initial_text: str) -> TuiState:
    return TuiState(
        visible_year=state.visible_year,
        visible_month=state.visible_month,
        selected_day=state.selected_day,
        selected_bucket=state.selected_bucket,
        mode="INSERT",
        edit_buffer=initial_text,
        status_message=state.status_message,
    )


def exit_insert_mode(state: TuiState, status_message: str = "") -> TuiState:
    return TuiState(
        visible_year=state.visible_year,
        visible_month=state.visible_month,
        selected_day=state.selected_day,
        selected_bucket=state.selected_bucket,
        mode="NORMAL",
        edit_buffer="",
        status_message=status_message,
    )


def serialize_bucket_text(items: list[str]) -> str:
    return " | ".join(items)


def parse_bucket_text(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_state.py src/mplan/tui_state.py
git commit -m "feat: add tui state primitives"
```

### Task 2: Add day navigation and visible-month-follow state transitions

**Files:**
- Modify: `src/mplan/tui_state.py`
- Test: `tests/test_tui_state.py`

**Interfaces:**
- Consumes: `TuiState`, `mplan.month_grid.build_month_grid()`
- Produces: `move_selection(state: TuiState, direction: Literal["left", "right", "up", "down"]) -> TuiState`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.tui_state import TuiState, move_selection


def test_move_selection_keeps_bucket_when_moving_between_days():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    state = state.__class__(**{**state.__dict__, "selected_bucket": "午"})
    moved = move_selection(state, "right")
    assert moved.selected_day == date(2026, 7, 13)
    assert moved.selected_bucket == "午"


def test_move_selection_moves_by_week_when_pressing_down():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    moved = move_selection(state, "down")
    assert moved.selected_day == date(2026, 7, 19)


def test_move_selection_switches_visible_month_when_crossing_boundary():
    state = TuiState.initial(selected_day=date(2026, 7, 31))
    moved = move_selection(state, "right")
    assert moved.selected_day == date(2026, 8, 1)
    assert (moved.visible_year, moved.visible_month) == (2026, 8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_state.py -v`
Expected: FAIL with `AttributeError` or missing `move_selection`

- [ ] **Step 3: Write minimal implementation**

```python
import calendar
from datetime import date
from typing import Literal

Direction = Literal["left", "right", "up", "down"]


def move_selection(state: TuiState, direction: Direction) -> TuiState:
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(state.visible_year, state.visible_month)
    row_index = 0
    col_index = 0
    for week_i, week in enumerate(weeks):
        for col_i, day in enumerate(week):
            if day == state.selected_day:
                row_index = week_i
                col_index = col_i
                break
        else:
            continue
        break

    deltas = {
        "left": (0, -1),
        "right": (0, 1),
        "up": (-1, 0),
        "down": (1, 0),
    }
    row_delta, col_delta = deltas[direction]
    next_day = weeks[row_index][col_index]
    target_row = row_index + row_delta
    target_col = col_index + col_delta
    if 0 <= target_row < len(weeks) and 0 <= target_col < len(weeks[target_row]):
        next_day = weeks[target_row][target_col]
    else:
        offset_days = {"left": -1, "right": 1, "up": -7, "down": 7}[direction]
        next_day = state.selected_day.fromordinal(state.selected_day.toordinal() + offset_days)

    return TuiState(
        visible_year=next_day.year,
        visible_month=next_day.month,
        selected_day=next_day,
        selected_bucket=state.selected_bucket,
        mode=state.mode,
        edit_buffer=state.edit_buffer,
        status_message=state.status_message,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_state.py src/mplan/tui_state.py
git commit -m "feat: add tui navigation state"
```

### Task 3: Add storage-backed bucket loading and saving helpers for the TUI

**Files:**
- Create: `src/mplan/tui_store.py`
- Test: `tests/test_tui_store.py`

**Interfaces:**
- Consumes: `mplan.storage.Store`, `mplan.models.PlannerItem`, `parse_bucket_text()`, `serialize_bucket_text()`
- Produces: `load_bucket_text(store: Store, day: date, bucket: str) -> str`, `save_bucket_text(store: Store, day: date, bucket: str, raw: str) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.tui_store import load_bucket_text, save_bucket_text


def test_load_bucket_text_joins_items_in_bucket(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文"))
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="回消息"))
    assert load_bucket_text(store, date(2026, 7, 12), "早") == "看论文 | 回消息"


def test_save_bucket_text_replaces_existing_bucket_items(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="旧内容"))
    saved = save_bucket_text(store, date(2026, 7, 12), "午", "改简历 | 练口语")
    items = [item.text for item in store.list_day_items(date(2026, 7, 12)) if item.bucket == "午"]
    assert saved == ["改简历", "练口语"]
    assert items == ["改简历", "练口语"]


def test_save_bucket_text_clears_bucket_when_input_is_empty(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料"))
    save_bucket_text(store, date(2026, 7, 12), "晚", " | ")
    items = [item for item in store.list_day_items(date(2026, 7, 12)) if item.bucket == "晚"]
    assert items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_store.py -v`
Expected: FAIL with `ModuleNotFoundError` for `mplan.tui_store`

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.tui_state import parse_bucket_text, serialize_bucket_text


def load_bucket_text(store: Store, day: date, bucket: str) -> str:
    items = [item.text for item in store.list_day_items(day) if item.bucket == bucket]
    return serialize_bucket_text(items)


def save_bucket_text(store: Store, day: date, bucket: str, raw: str) -> list[str]:
    parsed = parse_bucket_text(raw)
    store.delete_day_bucket(day, bucket)
    for text in parsed:
        store.upsert_planner_item(PlannerItem.new(day=day, bucket=bucket, text=text))
    return parsed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_store.py src/mplan/tui_store.py
git commit -m "feat: add tui storage helpers"
```

### Task 4: Extend month-grid view models for selected bucket highlighting

**Files:**
- Modify: `src/mplan/month_grid.py`
- Test: `tests/test_month_grid.py`

**Interfaces:**
- Consumes: existing `DayViewModel`, `DayCell`, `build_month_grid()`
- Produces: `DayCell.selected_bucket: str | None`, `build_month_grid(..., selected_bucket: str) -> MonthGrid`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.month_grid import DayViewModel, build_month_grid


def test_build_month_grid_marks_selected_bucket_on_selected_day():
    grid = build_month_grid(
        2026,
        7,
        selected_day=date(2026, 7, 12),
        selected_bucket="午",
        day_data={
            date(2026, 7, 12): DayViewModel(
                imported_events=[],
                morning=["看论文"],
                afternoon=["改简历"],
                evening=[],
            )
        },
    )
    selected = next(cell for week in grid.weeks for cell in week if cell.selected)
    assert selected.selected_bucket == "午"


def test_build_month_grid_does_not_mark_bucket_on_unselected_days():
    grid = build_month_grid(
        2026,
        7,
        selected_day=date(2026, 7, 12),
        selected_bucket="晚",
        day_data={},
    )
    other = next(cell for week in grid.weeks for cell in week if cell.day == date(2026, 7, 13))
    assert other.selected_bucket is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_month_grid.py -v`
Expected: FAIL because `build_month_grid()` does not accept `selected_bucket`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class DayCell:
    day: date
    imported_events: list[str]
    morning: list[str]
    afternoon: list[str]
    evening: list[str]
    in_month: bool
    selected: bool
    selected_bucket: str | None


def build_month_grid(
    year: int,
    month: int,
    selected_day: date,
    day_data: dict[date, DayViewModel],
    selected_bucket: str = "早",
) -> MonthGrid:
    ...
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_month_grid.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_grid.py src/mplan/month_grid.py
git commit -m "feat: track selected bucket in month grid"
```

### Task 5: Add pure render-model helpers for header, footer, and compact-screen fallback

**Files:**
- Create: `src/mplan/tui_render.py`
- Test: `tests/test_tui_render.py`

**Interfaces:**
- Consumes: `TuiState`, `Store`, `SyncEngine`, `build_month_grid()`, `load_bucket_text()`
- Produces: `build_screen_view(store, sync_engine, state: TuiState, width: int, height: int) -> dict[str, object]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.sync import SyncEngine
from mplan.tui_render import build_screen_view
from mplan.tui_state import TuiState, enter_insert_mode


class DummyBridge:
    def list_events(self, year: int, month: int):
        return []

    def upsert_event(self, *args, **kwargs):
        raise AssertionError("not used")


def test_build_screen_view_returns_footer_hints_in_normal_mode(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    view = build_screen_view(store, SyncEngine(store, DummyBridge()), state, width=140, height=40)
    assert "NORMAL" in view["header"]
    assert "Tab" in view["footer"]


def test_build_screen_view_includes_edit_buffer_in_insert_mode(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文"))
    state = enter_insert_mode(TuiState.initial(selected_day=date(2026, 7, 12)), "看论文")
    view = build_screen_view(store, SyncEngine(store, DummyBridge()), state, width=140, height=40)
    assert "INSERT" in view["header"]
    assert view["editor_text"] == "看论文"


def test_build_screen_view_marks_compact_mode_when_terminal_is_small(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    view = build_screen_view(store, SyncEngine(store, DummyBridge()), state, width=60, height=20)
    assert view["layout"] == "compact"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_render.py -v`
Expected: FAIL with `ModuleNotFoundError` for `mplan.tui_render`

- [ ] **Step 3: Write minimal implementation**

```python
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
            day_data[day] = DayViewModel(imported_events=imported, morning=[], afternoon=[], evening=[])

    grid = build_month_grid(
        state.visible_year,
        state.visible_month,
        selected_day=state.selected_day,
        selected_bucket=state.selected_bucket,
        day_data=day_data,
    )
    return {
        "header": f"{state.visible_year}-{state.visible_month:02d} {state.mode}",
        "grid": grid,
        "layout": "compact" if width < (7 * 16 + 8) else "full",
        "footer": f"{state.selected_day.isoformat()} {state.selected_bucket} 方向键移动 Tab切换 i编辑 Esc保存 s同步 q退出",
        "editor_text": state.edit_buffer if state.mode == "INSERT" else load_bucket_text(
            store, state.selected_day, state.selected_bucket
        ),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui_render.py src/mplan/tui_render.py
git commit -m "feat: add tui render models"
```

### Task 6: Add curses runtime loop and keyboard handling

**Files:**
- Create: `src/mplan/tui.py`
- Test: `tests/test_tui.py`

**Interfaces:**
- Consumes: `TuiState`, `move_selection()`, `cycle_bucket()`, `enter_insert_mode()`, `exit_insert_mode()`, `load_bucket_text()`, `save_bucket_text()`, `build_screen_view()`
- Produces: `run_tui(store, sync_engine) -> int`, `handle_keypress(state: TuiState, key: int, store, sync_engine) -> tuple[TuiState, bool]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.tui import handle_keypress
from mplan.tui_state import TuiState


class DummyStore:
    pass


class DummySyncEngine:
    def __init__(self):
        self.calls = []

    def sync_month(self, year: int, month: int):
        self.calls.append((year, month))
        return type("Report", (), {"imported_count": 0, "exported_count": 0, "updated_count": 0, "warning": ""})()


def test_handle_keypress_tab_cycles_bucket():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    updated, should_quit = handle_keypress(state, 9, DummyStore(), DummySyncEngine())
    assert updated.selected_bucket == "午"
    assert should_quit is False


def test_handle_keypress_q_requests_exit():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    updated, should_quit = handle_keypress(state, ord("q"), DummyStore(), DummySyncEngine())
    assert updated == state
    assert should_quit is True


def test_handle_keypress_s_runs_month_sync():
    sync_engine = DummySyncEngine()
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    updated, should_quit = handle_keypress(state, ord("s"), DummyStore(), sync_engine)
    assert sync_engine.calls == [(2026, 7)]
    assert "已同步" in updated.status_message
    assert should_quit is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py -v`
Expected: FAIL with `ModuleNotFoundError` for `mplan.tui`

- [ ] **Step 3: Write minimal implementation**

```python
import curses

from mplan.tui_render import build_screen_view
from mplan.tui_state import cycle_bucket, enter_insert_mode, exit_insert_mode, move_selection
from mplan.tui_store import load_bucket_text, save_bucket_text


def handle_keypress(state, key: int, store, sync_engine):
    if state.mode == "NORMAL":
        if key == ord("q"):
            return state, True
        if key == ord("\t"):
            state = state.__class__(**{**state.__dict__, "selected_bucket": cycle_bucket(state.selected_bucket)})
            return state, False
        if key == ord("i"):
            return enter_insert_mode(
                state,
                load_bucket_text(store, state.selected_day, state.selected_bucket),
            ), False
        if key == ord("s"):
            report = sync_engine.sync_month(state.visible_year, state.visible_month)
            status = f"已同步: 导入 {report.imported_count}，导出 {report.exported_count}，更新 {report.updated_count}"
            return state.__class__(**{**state.__dict__, "status_message": status}), False
        arrow_map = {
            curses.KEY_LEFT: "left",
            curses.KEY_RIGHT: "right",
            curses.KEY_UP: "up",
            curses.KEY_DOWN: "down",
        }
        if key in arrow_map:
            return move_selection(state, arrow_map[key]), False
        return state, False

    if key == 27:
        save_bucket_text(store, state.selected_day, state.selected_bucket, state.edit_buffer)
        return exit_insert_mode(state, "已保存"), False
    if key in (curses.KEY_BACKSPACE, 127):
        return state.__class__(**{**state.__dict__, "edit_buffer": state.edit_buffer[:-1]}), False
    if 32 <= key <= 126 or key > 127:
        return state.__class__(**{**state.__dict__, "edit_buffer": state.edit_buffer + chr(key)}), False
    return state, False


def run_tui(store, sync_engine) -> int:
    def _main(stdscr):
        state = __import__("mplan.tui_state", fromlist=["TuiState"]).TuiState.initial(
            selected_day=__import__("datetime").date.today()
        )
        while True:
            stdscr.clear()
            view = build_screen_view(store, sync_engine, state, *stdscr.getmaxyx()[::-1])
            stdscr.addstr(0, 0, view["header"])
            stdscr.addstr(1, 0, view["footer"])
            if state.mode == "INSERT":
                stdscr.addstr(2, 0, view["editor_text"])
            stdscr.refresh()
            state, should_quit = handle_keypress(state, stdscr.getch(), store, sync_engine)
            if should_quit:
                break
        return 0

    return curses.wrapper(_main)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui.py src/mplan/tui.py
git commit -m "feat: add tui runtime loop"
```

### Task 7: Route the default app entrypoint through the new TUI

**Files:**
- Modify: `src/mplan/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `run_tui(store, sync_engine)`
- Produces: `launch_app()` invoking the TUI runtime instead of `run_app()`

- [ ] **Step 1: Write the failing tests**

```python
from mplan.cli import launch_app


def test_launch_app_uses_tui_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.build_store", lambda: "store")
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: ("sync", store))
    monkeypatch.setattr("mplan.cli.run_tui", lambda store, sync_engine: calls.append((store, sync_engine)) or 0)
    assert launch_app() == 0
    assert calls == [("store", ("sync", "store"))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_launch_app_uses_tui_runtime -v`
Expected: FAIL because `launch_app()` still calls the old prompt app

- [ ] **Step 3: Write minimal implementation**

```python
from mplan.tui import run_tui


def launch_app() -> int:
    store = build_store()
    sync_engine = build_sync_engine(store)
    return run_tui(store, sync_engine)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_launch_app_uses_tui_runtime -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py src/mplan/cli.py
git commit -m "feat: launch tui by default"
```

### Task 8: Verify the integrated behavior and refresh user-facing docs

**Files:**
- Modify: `README.md`
- Modify: `tests/test_tui.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: final TUI runtime and CLI behavior
- Produces: smoke coverage for startup behavior, updated user docs for navigation and save/sync semantics

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.tui import handle_keypress
from mplan.tui_state import TuiState, enter_insert_mode


class DummyStore:
    def __init__(self):
        self.saved = []


class DummySyncEngine:
    def sync_month(self, year: int, month: int):
        return type("Report", (), {"imported_count": 1, "exported_count": 0, "updated_count": 0, "warning": ""})()


def test_handle_keypress_escape_saves_and_returns_to_normal(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.tui.save_bucket_text", lambda store, day, bucket, raw: calls.append((day, bucket, raw)) or ["看论文"])
    state = enter_insert_mode(TuiState.initial(selected_day=date(2026, 7, 12)), "看论文")
    updated, should_quit = handle_keypress(state, 27, DummyStore(), DummySyncEngine())
    assert calls == [(date(2026, 7, 12), "早", "看论文")]
    assert updated.mode == "NORMAL"
    assert updated.status_message == "已保存"
    assert should_quit is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui.py::test_handle_keypress_escape_saves_and_returns_to_normal -v`
Expected: FAIL until the runtime and save path are wired correctly

- [ ] **Step 3: Write minimal implementation**

```markdown
## TUI Controls

```bash
mplan
```

- Arrow keys move between days
- `Tab` switches `早 / 午 / 晚`
- `i` enters insert mode for the selected bucket
- `Esc` saves the selected bucket locally and returns to normal mode
- `s` syncs the visible month with Calendar
- `q` quits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_tui.py tests/test_cli.py README.md
git commit -m "docs: document tui controls"
```

