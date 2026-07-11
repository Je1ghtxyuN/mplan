# mplan Command Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the month-grid `mplan` UI as the main screen while adding `NORMAL / INSERT / COMMAND` flow, a centered day-detail overlay, short+long `:` commands, and task-level editing that preserves planner item identity for safe Calendar sync updates.

**Architecture:** Extend `src/mplan/app.py` into a three-mode controller with a day-detail overlay view layered over the existing month grid. Replace bucket-string rewriting with task-level storage helpers so adding or editing one task does not delete sibling tasks or lose `external_event_id`, and move sync/quit/view/month actions into a small command parser used by `COMMAND` mode.

**Tech Stack:** Python 3.14, existing terminal stdout/input flow in `src/mplan/app.py`, SQLite store in `src/mplan/storage.py`, Apple Calendar bridge in `src/mplan/calendar_bridge.py`, `pytest`

## Global Constraints

- Keep the existing month grid as the main display
- Restrict `NORMAL` mode to navigation and bucket selection
- Add a bottom `COMMAND` mode entered with `:`
- Support both short and long command aliases
- Add `:sq` as sync-and-quit
- Replace the old prompt-style `v DD` / `e DD` interaction in the TUI with commands targeting the currently selected day
- Add a centered day-detail view that expands the full selected day while visually dimming the month grid behind it
- Make `i` create a new task in the active bucket instead of rewriting the whole bucket line
- Style the bottom statusline with distinct mode colors and a more `nvim`-like feel
- Do not replace the grid UI with a separate full-screen runtime
- Keep `src/mplan/app.py` as the default interactive runtime launched by `mplan`
- The bottom line is always visible, even when the terminal is short
- The overlay is a view state, not a fourth editing mode
- `NORMAL` mode is used only for selection
- Sync, quit, month switching, and detail view are triggered through `COMMAND`
- `Enter` or `:v` opens a centered day-detail overlay
- Existing tasks must keep their identity strongly enough for sync to update Calendar events instead of duplicating them

## File Structure

- `src/mplan/models.py`
  - Add item-level mutation helpers that preserve `id`, `created_at`, and `external_event_id`
- `src/mplan/storage.py`
  - Add focused CRUD helpers for list-by-bucket, create-one, update-one, delete-one
- `src/mplan/grid_edit.py`
  - Replace bucket-line save helpers with task-level insert/update helpers and statusline/color helpers for three modes
- `src/mplan/detail_view.py`
  - New pure renderer for the centered day-detail overlay
- `src/mplan/app.py`
  - Extend state machine for `COMMAND`, overlay visibility, selected overlay task, and task-level insert/edit flows
- `tests/test_storage.py`
  - Add storage tests for item identity preservation
- `tests/test_grid_edit.py`
  - Add focused tests for task draft helpers and statusline mode rendering
- `tests/test_detail_view.py`
  - Add overlay rendering tests
- `tests/test_app.py`
  - Add command-mode, overlay, and task-creation behavior tests
- `README.md`
  - Update controls and command descriptions

---

### Task 1: Add task-level planner item mutation helpers that preserve identity

**Files:**
- Modify: `src/mplan/models.py`
- Modify: `src/mplan/storage.py`
- Modify: `tests/test_storage.py`

**Interfaces:**
- Consumes: `mplan.models.PlannerItem`
- Produces: `PlannerItem.with_text(text: str) -> PlannerItem`, `Store.list_bucket_items(day: date, bucket: str) -> list[PlannerItem]`, `Store.create_planner_item(item: PlannerItem) -> PlannerItem`, `Store.update_planner_item(item: PlannerItem) -> PlannerItem`, `Store.delete_planner_item(item_id: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store


def test_update_planner_item_preserves_external_event_id(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    original = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧内容")
    original = store.create_planner_item(original)
    store.attach_external_event_id(original.id, "evt-123")

    reloaded = store.list_day_items(date(2026, 7, 10))[0]
    updated = reloaded.with_text("新内容")
    store.update_planner_item(updated)

    final = store.list_day_items(date(2026, 7, 10))[0]
    assert final.id == original.id
    assert final.text == "新内容"
    assert final.external_event_id == "evt-123"


def test_list_bucket_items_returns_only_requested_bucket(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="看论文"))
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历"))

    items = store.list_bucket_items(date(2026, 7, 10), "午")

    assert [item.text for item in items] == ["改简历"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_storage.py::test_update_planner_item_preserves_external_event_id tests/test_storage.py::test_list_bucket_items_returns_only_requested_bucket -q`
Expected: FAIL because `Store.create_planner_item`, `Store.update_planner_item`, `Store.list_bucket_items`, or `PlannerItem.with_text` do not exist

- [ ] **Step 3: Write the minimal implementation**

```python
# src/mplan/models.py
def with_text(self, text: str) -> "PlannerItem":
    return replace(self, text=text, updated_at=datetime.now(UTC))


# src/mplan/storage.py
def create_planner_item(self, item: PlannerItem) -> PlannerItem:
    return self.upsert_planner_item(item)


def update_planner_item(self, item: PlannerItem) -> PlannerItem:
    return self.upsert_planner_item(item)


def delete_planner_item(self, item_id: str) -> None:
    with self._connect() as conn:
        conn.execute("delete from planner_items where id = ?", (item_id,))


def list_bucket_items(self, day: date, bucket: str) -> list[PlannerItem]:
    return [item for item in self.list_day_items(day) if item.bucket == bucket]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_storage.py::test_update_planner_item_preserves_external_event_id tests/test_storage.py::test_list_bucket_items_returns_only_requested_bucket -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/models.py src/mplan/storage.py tests/test_storage.py
git commit -m "feat: add task-level planner item helpers"
```

### Task 2: Replace bucket-line save helpers with task-level insert and update helpers

**Files:**
- Modify: `src/mplan/grid_edit.py`
- Modify: `tests/test_grid_edit.py`

**Interfaces:**
- Consumes: `Store.create_planner_item`, `Store.update_planner_item`, `Store.list_bucket_items`, `PlannerItem.with_text`
- Produces: `GridMode = Literal["NORMAL", "INSERT", "COMMAND"]`, `InsertTarget = str | None`, `load_bucket_items(store, day: date, bucket: str) -> list[PlannerItem]`, `create_bucket_task(store, day: date, bucket: str, text: str) -> PlannerItem`, `update_bucket_task(store, item: PlannerItem, text: str) -> PlannerItem`, `build_statusline(mode: str, day: date, bucket: str, status: str, buffer: str = "") -> str`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan.grid_edit import build_statusline, create_bucket_task, update_bucket_task
from mplan.models import PlannerItem
from mplan.storage import Store


def test_create_bucket_task_adds_one_item_without_touching_existing_siblings(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧任务"))

    create_bucket_task(store, date(2026, 7, 10), "午", "新任务")

    items = store.list_bucket_items(date(2026, 7, 10), "午")
    assert [item.text for item in items] == ["旧任务", "新任务"]


def test_update_bucket_task_keeps_same_item_id(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    item = store.create_planner_item(
        PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧任务")
    )

    updated = update_bucket_task(store, item, "新任务")

    assert updated.id == item.id
    assert store.list_bucket_items(date(2026, 7, 10), "午")[0].text == "新任务"


def test_build_statusline_supports_command_mode_text():
    line = build_statusline("COMMAND", date(2026, 7, 10), "午", "", buffer=":sq")
    assert "COMMAND" in line
    assert ":sq" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py::test_create_bucket_task_adds_one_item_without_touching_existing_siblings tests/test_grid_edit.py::test_update_bucket_task_keeps_same_item_id tests/test_grid_edit.py::test_build_statusline_supports_command_mode_text -q`
Expected: FAIL because the task-level helpers or `COMMAND` statusline branch do not exist

- [ ] **Step 3: Write the minimal implementation**

```python
from mplan.models import PlannerItem

GridMode = Literal["NORMAL", "INSERT", "COMMAND"]


def load_bucket_items(store, day: date, bucket: PlannerBucket) -> list[PlannerItem]:
    return store.list_bucket_items(day, bucket)


def create_bucket_task(store, day: date, bucket: PlannerBucket, text: str) -> PlannerItem:
    return store.create_planner_item(PlannerItem.new(day=day, bucket=bucket, text=text.strip()))


def update_bucket_task(store, item: PlannerItem, text: str) -> PlannerItem:
    updated = item.with_text(text.strip())
    return store.update_planner_item(updated)


def build_statusline(mode: str, day: date, bucket: str, status: str, buffer: str = "") -> str:
    if mode == "INSERT":
        return f"INSERT | {day.isoformat()} | {bucket} | {buffer} | Esc保存"
    if mode == "COMMAND":
        return f"COMMAND | {day.isoformat()} | {bucket} | {buffer or ':'}"
    tail = status or "方向键移动 Tab切分区 Enter详情 i新建 :命令"
    return f"NORMAL | {day.isoformat()} | {bucket} | {tail}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py::test_create_bucket_task_adds_one_item_without_touching_existing_siblings tests/test_grid_edit.py::test_update_bucket_task_keeps_same_item_id tests/test_grid_edit.py::test_build_statusline_supports_command_mode_text -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/grid_edit.py tests/test_grid_edit.py
git commit -m "feat: switch grid editing to task-level helpers"
```

### Task 3: Add pure centered day-detail overlay renderer

**Files:**
- Create: `src/mplan/detail_view.py`
- Create: `tests/test_detail_view.py`

**Interfaces:**
- Consumes: `mplan.models.ImportedCalendarEvent`, `mplan.models.PlannerItem`
- Produces: `DetailViewModel`, `build_detail_view(day: date, bucket: str, imported_events: list[ImportedCalendarEvent], bucket_items: dict[str, list[PlannerItem]], selected_task_index: int | None, width: int, height: int) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, date

from mplan.detail_view import build_detail_view
from mplan.models import ImportedCalendarEvent, PlannerItem


def test_build_detail_view_shows_full_day_sections_and_active_bucket():
    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="午",
        imported_events=[
            ImportedCalendarEvent(
                id="evt-1",
                title="腾讯会议",
                starts_at=datetime.fromisoformat("2026-07-10T09:00:00"),
                ends_at=datetime.fromisoformat("2026-07-10T10:00:00"),
                calendar_name="工作",
            )
        ],
        bucket_items={
            "早": [PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="看论文")],
            "午": [PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")],
            "晚": [],
        },
        selected_task_index=None,
        width=60,
        height=16,
    )

    assert any("2026-07-10" in row for row in rows)
    assert any("正式日程" in row for row in rows)
    assert any("> 午" in row or ">午" in row for row in rows)
    assert any("改简历" in row for row in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_detail_view.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mplan.detail_view'`

- [ ] **Step 3: Write the minimal implementation**

```python
from dataclasses import dataclass
from datetime import date


def build_detail_view(day, bucket, imported_events, bucket_items, selected_task_index, width, height):
    rows = [f"┌ {'day':<{max(1, width - 4)}}" ]
    rows = [f"╔{'═' * (width - 2)}╗", f"║ {day.isoformat():<{width - 4}} ║", f"║ 正式日程{' ' * (width - 8)}║"]
    for event in imported_events:
        rows.append(f"║ {event.starts_at.strftime('%H:%M')} {event.title:<{width - 10}} ║")
    for section in ("早", "午", "晚"):
        marker = ">" if section == bucket else " "
        rows.append(f"║ {marker}{section} {' ' * (width - 6)}║")
        for item in bucket_items.get(section, []):
            rows.append(f"║   {item.text:<{width - 6}}║")
    rows = rows[: max(1, height - 1)]
    while len(rows) < height - 1:
        rows.append(f"║ {' ' * (width - 4)} ║")
    rows.append(f"╚{'═' * (width - 2)}╝")
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_detail_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/detail_view.py tests/test_detail_view.py
git commit -m "feat: add day detail overlay renderer"
```

### Task 4: Add command parsing and colorized statusline helpers

**Files:**
- Modify: `src/mplan/grid_edit.py`
- Modify: `tests/test_grid_edit.py`

**Interfaces:**
- Consumes: `GridMode`, `build_statusline(...)`
- Produces: `parse_command(raw: str) -> str`, `COMMAND_ALIASES: dict[str, str]`, `colorize_mode_label(mode: str) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from mplan.grid_edit import colorize_mode_label, parse_command


def test_parse_command_normalizes_short_and_long_aliases():
    assert parse_command(":s") == "sync"
    assert parse_command(":sync") == "sync"
    assert parse_command(":sq") == "syncquit"
    assert parse_command(":v") == "view"


def test_colorize_mode_label_wraps_normal_in_ansi_codes():
    label = colorize_mode_label("NORMAL")
    assert label.startswith("\x1b[")
    assert "NORMAL" in label
    assert label.endswith("\x1b[0m")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py::test_parse_command_normalizes_short_and_long_aliases tests/test_grid_edit.py::test_colorize_mode_label_wraps_normal_in_ansi_codes -q`
Expected: FAIL because `parse_command` and `colorize_mode_label` do not exist

- [ ] **Step 3: Write the minimal implementation**

```python
COMMAND_ALIASES = {
    "q": "quit",
    "quit": "quit",
    "s": "sync",
    "sync": "sync",
    "sq": "syncquit",
    "syncquit": "syncquit",
    "v": "view",
    "view": "view",
    "n": "next",
    "next": "next",
    "p": "prev",
    "prev": "prev",
}


def parse_command(raw: str) -> str:
    normalized = raw.strip()
    if normalized.startswith(":"):
        normalized = normalized[1:]
    return COMMAND_ALIASES.get(normalized, normalized)


def colorize_mode_label(mode: str) -> str:
    colors = {"NORMAL": "32", "INSERT": "34", "COMMAND": "33"}
    return f"\x1b[{colors.get(mode, '0')}m{mode}\x1b[0m"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_grid_edit.py::test_parse_command_normalizes_short_and_long_aliases tests/test_grid_edit.py::test_colorize_mode_label_wraps_normal_in_ansi_codes -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/grid_edit.py tests/test_grid_edit.py
git commit -m "feat: add command parser and mode colors"
```

### Task 5: Extend app state for command mode and day-detail overlay

**Files:**
- Modify: `src/mplan/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `parse_command`, `build_statusline`, `colorize_mode_label`, `build_detail_view`
- Produces: `_enter_command_mode(state: dict[str, object]) -> dict[str, object]`, `_handle_command_key(state: dict[str, object], key: str, command_func) -> dict[str, object]`, `_open_detail_view(state: dict[str, object]) -> dict[str, object]`, `_close_detail_view(state: dict[str, object]) -> dict[str, object]`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

from mplan import app


def test_handle_normal_command_colon_enters_command_mode():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "status": "",
    }

    updated = app._handle_normal_command(state, ":")

    assert updated["mode"] == "COMMAND"
    assert updated["command_buffer"] == ":"


def test_handle_normal_command_enter_opens_detail_overlay():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "status": "",
    }

    updated = app._handle_normal_command(state, "ENTER")

    assert updated["detail_open"] is True


def test_handle_command_key_executes_syncquit_command():
    calls = []
    state = {
        "mode": "COMMAND",
        "command_buffer": ":sq",
        "status": "",
    }

    updated = app._handle_command_key(
        state,
        "ENTER",
        command_func=lambda command: calls.append(command) or {"quit": True, "status": "已同步"},
    )

    assert calls == ["syncquit"]
    assert updated["quit"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_handle_normal_command_colon_enters_command_mode tests/test_app.py::test_handle_normal_command_enter_opens_detail_overlay tests/test_app.py::test_handle_command_key_executes_syncquit_command -q`
Expected: FAIL because command mode and overlay state are not yet implemented

- [ ] **Step 3: Write the minimal implementation**

```python
def _enter_command_mode(state):
    return {**state, "mode": "COMMAND", "command_buffer": ":"}


def _open_detail_view(state):
    return {**state, "detail_open": True, "detail_task_index": 0}


def _close_detail_view(state):
    return {**state, "detail_open": False, "detail_task_index": 0}


def _handle_command_key(state, key, command_func):
    if key == "ESC":
        return {**state, "mode": "NORMAL", "command_buffer": ""}
    if key == "BACKSPACE":
        return {**state, "command_buffer": state["command_buffer"][:-1] or ":"}
    if key == "ENTER":
        result = command_func(parse_command(state["command_buffer"]))
        return {**state, "mode": "NORMAL", "command_buffer": "", **result}
    if len(key) == 1 and key.isprintable():
        return {**state, "command_buffer": f"{state['command_buffer']}{key}"}
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_handle_normal_command_colon_enters_command_mode tests/test_app.py::test_handle_normal_command_enter_opens_detail_overlay tests/test_app.py::test_handle_command_key_executes_syncquit_command -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/app.py tests/test_app.py
git commit -m "feat: add command mode and detail overlay state"
```

### Task 6: Integrate task creation, overlay rendering, and command actions into the runtime

**Files:**
- Modify: `src/mplan/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `create_bucket_task`, `load_bucket_items`, `build_detail_view`, `_handle_command_key`
- Produces: `run_app(store, sync_engine) -> int` with `NORMAL / INSERT / COMMAND`, `Enter` detail overlay, `:q/:s/:sq/:v/:n/:p`, and task-level `i` insertion

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date
from types import SimpleNamespace

from mplan import app


def test_run_app_i_creates_new_task_without_deleting_existing_items(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 10)

    class FakeStore:
        def __init__(self):
            self.created = []
            self.deleted = []

        def list_days_in_month(self, year, month):
            return []

        def list_day_items(self, day):
            return []

        def list_bucket_items(self, day, bucket):
            return []

        def create_planner_item(self, item):
            self.created.append(item.text)
            return item

        def delete_planner_item(self, item_id):
            self.deleted.append(item_id)

    store = FakeStore()
    sync_engine = SimpleNamespace(pull_month=lambda year, month: [], sync_month=lambda year, month: SimpleNamespace(imported_count=0, exported_count=0, updated_count=0, warning=None))
    keys = iter(["i", "A", "ESC", ":", "q", "ENTER"])

    monkeypatch.setattr(app, "date", FixedDate)
    monkeypatch.setattr(app, "_read_key", lambda mode="NORMAL": next(keys))
    monkeypatch.setattr(app, "_render_app", lambda store, sync_engine, state: None)

    assert app.run_app(store, sync_engine) == 0
    assert store.created == ["A"]
    assert store.deleted == []


def test_run_app_view_command_opens_and_escape_closes_detail_overlay(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 10)

    states = []
    sync_engine = SimpleNamespace(pull_month=lambda year, month: [], sync_month=lambda year, month: SimpleNamespace(imported_count=0, exported_count=0, updated_count=0, warning=None))
    store = SimpleNamespace(list_days_in_month=lambda year, month: [], list_day_items=lambda day: [], list_bucket_items=lambda day, bucket: [], create_planner_item=lambda item: item)
    keys = iter([":", "v", "ENTER", "ESC", ":", "q", "ENTER"])

    monkeypatch.setattr(app, "date", FixedDate)
    monkeypatch.setattr(app, "_read_key", lambda mode="NORMAL": next(keys))
    monkeypatch.setattr(app, "_render_app", lambda store, sync_engine, state: states.append((state["mode"], state["detail_open"])))

    assert app.run_app(store, sync_engine) == 0
    assert ("NORMAL", True) in states
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_run_app_i_creates_new_task_without_deleting_existing_items tests/test_app.py::test_run_app_view_command_opens_and_escape_closes_detail_overlay -q`
Expected: FAIL because `run_app()` still treats `i` as bucket-string editing and does not route `:v` to the overlay

- [ ] **Step 3: Write the minimal implementation**

```python
if state["mode"] == "COMMAND":
    state = _handle_command_key(
        state,
        command,
        command_func=lambda command_name: _execute_command(state, command_name, sync_engine),
    )
    continue

if state["mode"] == "INSERT":
    if command == "ESC":
        if state.get("editing_item") is None:
            create_bucket_task(store, state["selected"], state["bucket"], state["buffer"])
        else:
            update_bucket_task(store, state["editing_item"], state["buffer"])
        state = {**state, "mode": "NORMAL", "buffer": "", "editing_item": None, "status": "已保存"}
        continue

if command == "i":
    state = {**state, "mode": "INSERT", "buffer": "", "editing_item": None, "status": ""}
elif command == "ENTER":
    state = _open_detail_view(state)
elif command == ":":
    state = _enter_command_mode(state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_app.py::test_run_app_i_creates_new_task_without_deleting_existing_items tests/test_app.py::test_run_app_view_command_opens_and_escape_closes_detail_overlay -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mplan/app.py tests/test_app.py
git commit -m "feat: integrate command overlay runtime"
```

### Task 7: Update docs and run full regression coverage

**Files:**
- Modify: `README.md`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: final runtime behavior from `src/mplan/app.py`
- Produces: updated controls docs and regression coverage for `mplan` launch path

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
Expected: FAIL until the final naming/wiring test exists

- [ ] **Step 3: Write the minimal implementation**

```markdown
## Month View Controls

- Arrow keys move between dates
- `Tab` switches the selected bucket across `早 / 午 / 晚`
- `Enter` opens the centered day-detail view
- `i` creates a new task in the active bucket
- `:` enters command mode
- `:q` / `:quit` exits
- `:s` / `:sync` syncs the visible month
- `:sq` / `:syncquit` syncs and exits
- `:v` / `:view` opens the day-detail view
- `Esc` closes the detail view or saves insert mode
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_cli.py tests/test_app.py
git commit -m "docs: describe command mode controls"
```

## Self-Review

- Spec coverage:
  - command mode, short/long aliases, and `:sq` are covered by Tasks 4, 5, and 7
  - centered day-detail overlay is covered by Tasks 3, 5, and 6
  - `i` creating new tasks rather than rewriting buckets is covered by Tasks 1, 2, and 6
  - sync-safe item identity preservation is covered by Tasks 1, 2, and 6
  - colored mode labels and `nvim`-like statusline are covered by Tasks 2, 4, and 5
- Placeholder scan:
  - no `TODO`, `TBD`, or implicit “handle appropriately” steps remain
- Type consistency:
  - later tasks consistently reference `Store.create_planner_item`, `Store.update_planner_item`, `create_bucket_task`, `update_bucket_task`, `build_detail_view`, and `_handle_command_key`
