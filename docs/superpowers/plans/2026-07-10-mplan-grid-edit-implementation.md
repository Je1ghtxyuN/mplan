# mplan Grid Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the existing month-grid terminal planner as the default UI while adding nvim-like keyboard navigation and a single-line bottom editor for editing the selected `早 / 午 / 晚` bucket.

**Architecture:** Extend the existing grid runtime in `src/mplan/app.py` instead of routing through the alternate full-screen TUI. Add a light state machine for selected day, selected bucket, and mode; reuse current month-grid rendering plus storage/sync layers; and reserve one bottom line for a status/editor bar that always stays visible.

**Tech Stack:** Python 3.14, existing terminal stdout/input flow in `src/mplan/app.py`, existing month-grid renderer, `pytest`

## Global Constraints

- Keep the existing month-grid rendering in `src/mplan/app.py` as the default interactive UI
- Add keyboard-driven navigation with arrow keys for day selection
- Add bucket selection with `Tab` across `早 / 午 / 晚`
- Add `NORMAL` and `INSERT` modes
- Edit the selected bucket through a single-line bottom editor bar
- Save locally on `Esc` and sync explicitly on `s`
- Preserve the existing month-grid appearance as much as possible
- Do not replace the default UI with the new `src/mplan/tui.py` runtime
- Do not edit individual items as separate cursor targets
- Keep the insert buffer single-line only in v1
- Keep `src/mplan/app.py` as the default interactive runtime launched by `mplan`
- `src/mplan/cli.py` should route `launch_app()` to `run_app()` rather than the alternate full-screen runtime
- Do not degrade the default display into day-number-only rows, selected-day-only detail output, or a non-grid full-screen TUI as the main experience
- The bottom bar must always remain visible
- If the terminal is short, trim the grid/body content before losing the bottom bar
- No sync happens automatically on save

---

### Task 1: Restore and lock the grid runtime as the default entrypoint

**Files:**
- Modify: `src/mplan/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `mplan.app.run_app(store, sync_engine) -> int`
- Produces: `launch_app() -> int` using the grid runtime by default

- [ ] **Step 1: Write the failing test**

```python
from mplan.cli import launch_app


def test_launch_app_uses_grid_app_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.build_store", lambda: "store")
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: ("sync", store))
    monkeypatch.setattr(
        "mplan.cli.run_app",
        lambda store, sync_engine: calls.append((store, sync_engine)) or 0,
    )

    assert launch_app() == 0
    assert calls == [("store", ("sync", "store"))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_cli.py::test_launch_app_uses_grid_app_runtime -q`
Expected: FAIL because `launch_app()` still routes to the alternate runtime or the test does not yet exist

- [ ] **Step 3: Write minimal implementation**

```python
from mplan.app import run_app


def launch_app() -> int:
    store = build_store()
    sync_engine = build_sync_engine(store)
    return run_app(store, sync_engine)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_cli.py::test_launch_app_uses_grid_app_runtime -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/cli.py tests/test_cli.py
git commit -m "fix: restore grid runtime as default"
```

### Task 2: Add pure grid-edit state helpers for bucket cycling, buffer parsing, and statusline text

**Files:**
- Create: `src/mplan/grid_edit.py`
- Test: `tests/test_grid_edit.py`

**Interfaces:**
- Consumes: `mplan.models.PlannerBucket`
- Produces: `GridMode = Literal["NORMAL", "INSERT"]`, `cycle_bucket(bucket: str) -> str`, `serialize_bucket_items(items: list[str]) -> str`, `parse_bucket_buffer(raw: str) -> list[str]`, `build_statusline(mode: str, day: date, bucket: str, status: str, buffer: str = "") -> str`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from mplan.grid_edit import (
    build_statusline,
    cycle_bucket,
    parse_bucket_buffer,
    serialize_bucket_items,
)


def test_cycle_bucket_wraps_through_three_buckets():
    assert cycle_bucket("早") == "午"
    assert cycle_bucket("午") == "晚"
    assert cycle_bucket("晚") == "早"


def test_buffer_round_trip_uses_pipe_separator():
    assert serialize_bucket_items(["看论文", "回消息"]) == "看论文 | 回消息"
    assert parse_bucket_buffer(" 看论文 |  | 回消息 ") == ["看论文", "回消息"]


def test_statusline_uses_mode_first_nvim_like_text():
    line = build_statusline("NORMAL", date(2026, 7, 10), "午", "已保存")
    assert "NORMAL" in line
    assert "2026-07-10" in line
    assert "午" in line
    assert "已保存" in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mplan.grid_edit'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import date
from typing import Literal

GridMode = Literal["NORMAL", "INSERT"]
BUCKET_ORDER = ("早", "午", "晚")


def cycle_bucket(bucket: str) -> str:
    index = BUCKET_ORDER.index(bucket)
    return BUCKET_ORDER[(index + 1) % len(BUCKET_ORDER)]


def serialize_bucket_items(items: list[str]) -> str:
    return " | ".join(items)


def parse_bucket_buffer(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def build_statusline(mode: str, day: date, bucket: str, status: str, buffer: str = "") -> str:
    if mode == "INSERT":
        return f"{mode} | {day.isoformat()} | {bucket} | {buffer} | Esc保存"
    tail = status or "方向键移动 Tab切分区 i编辑 s同步 q退出"
    return f"{mode} | {day.isoformat()} | {bucket} | {tail}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/grid_edit.py tests/test_grid_edit.py
git commit -m "feat: add grid edit state helpers"
```

### Task 3: Add storage-backed bucket load/save helpers for the grid editor

**Files:**
- Modify: `src/mplan/grid_edit.py`
- Test: `tests/test_grid_edit.py`

**Interfaces:**
- Consumes: `mplan.storage.Store`, `mplan.models.PlannerItem`, `parse_bucket_buffer()`, `serialize_bucket_items()`
- Produces: `load_bucket_buffer(store, day: date, bucket: str) -> str`, `save_bucket_buffer(store, day: date, bucket: str, raw: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from mplan.grid_edit import load_bucket_buffer, save_bucket_buffer
from mplan.models import PlannerItem
from mplan.storage import Store


def test_load_bucket_buffer_joins_bucket_items(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历"))
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="练口语"))
    assert load_bucket_buffer(store, date(2026, 7, 10), "午") == "改简历 | 练口语"


def test_save_bucket_buffer_replaces_one_bucket_only(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="看论文"))
    store.upsert_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧内容"))
    save_bucket_buffer(store, date(2026, 7, 10), "午", "改简历 | 练口语")
    early = [item.text for item in store.list_day_items(date(2026, 7, 10)) if item.bucket == "早"]
    noon = [item.text for item in store.list_day_items(date(2026, 7, 10)) if item.bucket == "午"]
    assert early == ["看论文"]
    assert noon == ["改简历", "练口语"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py -q`
Expected: FAIL because the helper functions do not exist

- [ ] **Step 3: Write minimal implementation**

```python
from mplan.models import PlannerItem


def load_bucket_buffer(store, day: date, bucket: str) -> str:
    items = [item.text for item in store.list_day_items(day) if item.bucket == bucket]
    return serialize_bucket_items(items)


def save_bucket_buffer(store, day: date, bucket: str, raw: str) -> list[str]:
    parsed = parse_bucket_buffer(raw)
    store.delete_day_bucket(day, bucket)
    for text in parsed:
        store.upsert_planner_item(PlannerItem.new(day=day, bucket=bucket, text=text))
    return parsed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/grid_edit.py tests/test_grid_edit.py
git commit -m "feat: add grid bucket load save helpers"
```

### Task 4: Extend month-grid rendering to show the selected bucket inside the selected cell

**Files:**
- Modify: `src/mplan/month_grid.py`
- Modify: `tests/test_month_grid.py`

**Interfaces:**
- Consumes: `DayCell.selected_bucket`, `render_day_cell(cell, width: int, height: int) -> list[str]`
- Produces: selected bucket marker inside the selected day cell, while preserving grid layout

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from mplan.month_grid import DayCell, render_day_cell


def test_render_day_cell_marks_selected_bucket_inside_selected_day():
    cell = DayCell(
        day=date(2026, 7, 10),
        imported_events=[],
        morning=["看论文"],
        afternoon=["改简历"],
        evening=[],
        in_month=True,
        selected=True,
        selected_bucket="午",
    )

    lines = render_day_cell(cell, width=20, height=8)
    assert any(">午:" in line for line in lines)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_month_grid.py::test_render_day_cell_marks_selected_bucket_inside_selected_day -q`
Expected: FAIL because selected bucket markup is not rendered

- [ ] **Step 3: Write minimal implementation**

```python
def render_day_cell(cell: DayCell, width: int, height: int) -> list[str]:
    ...
    content_lines.extend(
        _wrap_block("早:" if cell.selected_bucket != "早" else ">早:", cell.morning, inner_width)
    )
    content_lines.extend(
        _wrap_block("午:" if cell.selected_bucket != "午" else ">午:", cell.afternoon, inner_width)
    )
    content_lines.extend(
        _wrap_block("晚:" if cell.selected_bucket != "晚" else ">晚:", cell.evening, inner_width)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_month_grid.py::test_render_day_cell_marks_selected_bucket_inside_selected_day -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/month_grid.py tests/test_month_grid.py
git commit -m "feat: highlight selected bucket in grid"
```

### Task 5: Add keyboard state and bottom statusline to the grid app while preserving the grid

**Files:**
- Modify: `src/mplan/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `build_month_grid()`, `render_day_cell()`, `cycle_bucket()`, `build_statusline()`, `load_bucket_buffer()`, `save_bucket_buffer()`
- Produces: `run_app(store, sync_engine) -> int` with `NORMAL` / `INSERT`, arrow-key navigation, `Tab` bucket cycling, `i` insert, `Esc` save, bottom statusline

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from mplan.app import _handle_normal_command, _handle_insert_key


def test_handle_normal_command_tab_cycles_bucket():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "早",
        "mode": "NORMAL",
        "buffer": "",
        "status": "",
    }

    updated = _handle_normal_command(state, "\t")
    assert updated["bucket"] == "午"


def test_handle_insert_key_escape_saves_and_returns_normal(tmp_path):
    saved = []
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "INSERT",
        "buffer": "改简历 | 练口语",
        "status": "",
    }

    updated = _handle_insert_key(
        state,
        "ESC",
        save_func=lambda day, bucket, raw: saved.append((day, bucket, raw)),
    )
    assert saved == [(date(2026, 7, 10), "午", "改简历 | 练口语")]
    assert updated["mode"] == "NORMAL"
    assert updated["status"] == "已保存"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py -q`
Expected: FAIL because the helper functions and tests do not exist

- [ ] **Step 3: Write minimal implementation**

```python
def _handle_normal_command(state, command: str):
    if command == "\t":
        return {**state, "bucket": cycle_bucket(state["bucket"])}
    ...


def _handle_insert_key(state, key: str, save_func):
    if key == "ESC":
        save_func(state["selected"], state["bucket"], state["buffer"])
        return {**state, "mode": "NORMAL", "status": "已保存"}
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/app.py tests/test_app.py
git commit -m "feat: add grid keyboard editor state"
```

### Task 6: Preserve bottom-bar visibility and visible-day month content under constrained terminal sizes

**Files:**
- Modify: `src/mplan/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `_print_month(...)`, bottom statusline rendering
- Produces: grid/body trimming that keeps one bottom bar visible while preserving visible-day content in the main grid

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from mplan.app import _fit_grid_rows_for_statusline


def test_fit_grid_rows_for_statusline_keeps_last_line_for_status():
    rows = [f"row-{index}" for index in range(20)]
    fitted = _fit_grid_rows_for_statusline(rows, total_lines=10)
    assert len(fitted) == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_fit_grid_rows_for_statusline_keeps_last_line_for_status -q`
Expected: FAIL because the helper does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def _fit_grid_rows_for_statusline(rows: list[str], total_lines: int) -> list[str]:
    available = max(0, total_lines - 1)
    return rows[:available]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_fit_grid_rows_for_statusline_keeps_last_line_for_status -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/app.py tests/test_app.py
git commit -m "fix: keep statusline visible in grid app"
```

### Task 7: Document the grid-edit controls and verify the integrated behavior

**Files:**
- Modify: `README.md`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: final grid runtime behavior
- Produces: updated docs for arrow keys / Tab / i / Esc / s / q, final smoke coverage

- [ ] **Step 1: Write the failing test**

```python
from mplan.cli import launch_app


def test_launch_app_still_uses_grid_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.build_store", lambda: "store")
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: ("sync", store))
    monkeypatch.setattr("mplan.cli.run_app", lambda store, sync_engine: calls.append((store, sync_engine)) or 0)
    assert launch_app() == 0
    assert calls == [("store", ("sync", "store"))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_cli.py::test_launch_app_still_uses_grid_runtime -q`
Expected: FAIL until the test exists and the final wiring remains correct

- [ ] **Step 3: Write minimal implementation**

```markdown
## Month View Controls

- Arrow keys move between dates
- `Tab` switches `早 / 午 / 晚`
- `i` enters bottom-bar edit mode for the selected bucket
- `Esc` saves and returns to normal mode
- `s` syncs the visible month
- `q` quits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py tests/test_app.py tests/test_month_grid.py tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_cli.py tests/test_app.py
git commit -m "docs: describe grid editor controls"
```
