# mplan iCloud Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `mplan` always sync planner events into `iCloud > mplan`, automatically create that calendar when missing, and migrate previously owned local-calendar events into iCloud.

**Architecture:** Keep the change centered in `CalendarBridge` so iCloud source detection, target-calendar creation, owned-event upsert, and migration rules all live in one boundary around AppleScript. `SyncEngine` keeps calling the bridge, but it learns enough migration metadata to update `external_event_id` safely, while `doctor` and `README` surface the stricter iCloud-only behavior to users.

**Tech Stack:** Python, sqlite3, AppleScript via `osascript`, pytest

## Global Constraints

- `mplan` never writes planner events into an arbitrary writable calendar
- `mplan` uses a dedicated iCloud calendar named `mplan`
- if that calendar does not exist, `mplan` creates it automatically under the user's iCloud calendars
- if no writable iCloud calendar/account is available, `mplan` fails with a clear error instead of silently writing to `On My Mac`
- only migrate events whose metadata identifies them as `source: "mplan"`
- never delete or rewrite unrelated user events
- never migrate non-owned events imported from other calendars
- new event creation must always target `iCloud > mplan`

---

### Task 1: iCloud Target Calendar Resolution

**Files:**
- Modify: `src/mplan/calendar_bridge.py`
- Test: `tests/test_calendar_bridge.py`

**Interfaces:**
- Consumes: existing `CalendarBridge._run_script(script: str) -> str`
- Produces: `CalendarBridge.ensure_target_calendar() -> str`, `CalendarBridge.calendar_status() -> tuple[bool, str]`

- [ ] **Step 1: Write the failing tests**

```python
def test_ensure_target_calendar_uses_existing_icloud_mplan(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: captured.setdefault("script", script) or "iCloud::mplan",
    )

    assert bridge.ensure_target_calendar() == "iCloud::mplan"
    assert "set targetCalendarName to \"mplan\"" in captured["script"]
    assert "iCloud" in captured["script"]


def test_calendar_status_reports_icloud_target(monkeypatch):
    bridge = CalendarBridge()
    monkeypatch.setattr(bridge, "_run_script", lambda script: "ok::iCloud::mplan")

    ok, detail = bridge.calendar_status()

    assert ok is True
    assert detail == "iCloud::mplan"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_ensure_target_calendar_uses_existing_icloud_mplan tests/test_calendar_bridge.py::test_calendar_status_reports_icloud_target -q`
Expected: FAIL with `AttributeError` because `ensure_target_calendar` / `calendar_status` do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
class CalendarBridge:
    TARGET_CALENDAR_NAME = "mplan"

    def ensure_target_calendar(self) -> str:
        script = f"""
set targetCalendarName to "{self.TARGET_CALENDAR_NAME}"
tell application "Calendar"
    set matchingCalendar to missing value
    repeat with cal in calendars
        try
            if name of cal is targetCalendarName and (name of its container) contains "iCloud" and writable of cal then
                set matchingCalendar to cal
                exit repeat
            end if
        end try
    end repeat
    if matchingCalendar is not missing value then
        return "iCloud::" & (name of matchingCalendar)
    end if
    error "未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步"
end tell
"""
        return self._run_script(script)

    def calendar_status(self) -> tuple[bool, str]:
        try:
            detail = self.ensure_target_calendar()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return False, str(exc)
        return True, detail
```

- [ ] **Step 4: Expand implementation to create `iCloud > mplan` when missing**

```python
def ensure_target_calendar(self) -> str:
    script = f"""
set targetCalendarName to "{self.TARGET_CALENDAR_NAME}"
tell application "Calendar"
    set iCloudSource to missing value
    set matchingCalendar to missing value
    repeat with cal in calendars
        try
            set containerName to name of its container
            if containerName contains "iCloud" then
                set iCloudSource to its container
                if name of cal is targetCalendarName and writable of cal then
                    set matchingCalendar to cal
                    exit repeat
                end if
            end if
        end try
    end repeat
    if matchingCalendar is not missing value then return "iCloud::" & name of matchingCalendar
    if iCloudSource is missing value then error "未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步"
    set matchingCalendar to make new calendar at end of calendars with properties {{name:targetCalendarName, container:iCloudSource}}
    return "iCloud::" & name of matchingCalendar
end tell
"""
    return self._run_script(script)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mplan/calendar_bridge.py tests/test_calendar_bridge.py
git commit -m "feat: target dedicated icloud calendar"
```

### Task 2: Migrate Old Owned Events Into iCloud

**Files:**
- Modify: `src/mplan/calendar_bridge.py`
- Modify: `src/mplan/sync.py`
- Test: `tests/test_calendar_bridge.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: `CalendarBridge.ensure_target_calendar() -> str`, `PlannerItem.external_event_id: str | None`
- Produces: `CalendarBridge.upsert_owned_event(item: PlannerItem, order_index: int) -> tuple[str, str | None]`

- [ ] **Step 1: Write the failing tests**

```python
def test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="改简历")
    item = item.with_external_event_id("local-evt-1")
    monkeypatch.setattr(bridge, "_run_script", lambda script: '{"event_id":"icloud-evt-1","deleted_event_id":"local-evt-1"}')

    event_id, deleted_event_id = bridge.upsert_owned_event(item, order_index=0)

    assert event_id == "icloud-evt-1"
    assert deleted_event_id == "local-evt-1"


def test_sync_month_updates_external_event_id_after_migration():
    ...
    assert fake_store.attached == [("item-1", "icloud-evt-1")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration tests/test_sync.py::test_sync_month_updates_external_event_id_after_migration -q`
Expected: FAIL because `upsert_owned_event` still returns a bare string and `SyncEngine.push_day()` does not handle migration results

- [ ] **Step 3: Write minimal bridge implementation**

```python
def upsert_owned_event(self, item: PlannerItem, order_index: int) -> tuple[str, str | None]:
    title = self.owned_title_for(item)
    starts_at, ends_at = self.event_window_for(item, order_index)
    metadata = ...
    self.ensure_target_calendar()
    script = f"""
...
return "{{\\"event_id\\":\\"" & uid of targetEvent & "\\",\\"deleted_event_id\\":" & my nullable_event_id(deletedEventId) & "}}"
"""
    payload = json.loads(self._run_script(script))
    return payload["event_id"], payload.get("deleted_event_id")
```

- [ ] **Step 4: Complete migration logic in AppleScript and sync code**

```python
def push_day(self, day: date) -> None:
    items = self.store.list_day_items(day)
    bucket_counts = {"早": 0, "午": 0, "晚": 0}
    for item in items:
        order_index = bucket_counts[item.bucket]
        event_id, _deleted_event_id = self.bridge.upsert_owned_event(item, order_index=order_index)
        self.store.attach_external_event_id(item.id, event_id)
        bucket_counts[item.bucket] += 1
```

AppleScript requirements for `upsert_owned_event`:

```applescript
-- if targetEventId resolves inside iCloud::mplan, update in place
-- else if targetEventId resolves in a non-iCloud calendar and notes identify source "mplan",
-- make/update new event in iCloud::mplan, remember old uid, delete old event
-- else create new event in iCloud::mplan
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py tests/test_sync.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mplan/calendar_bridge.py src/mplan/sync.py tests/test_calendar_bridge.py tests/test_sync.py
git commit -m "feat: migrate owned calendar events to icloud"
```

### Task 3: Doctor Output and User Docs

**Files:**
- Modify: `src/mplan/doctor.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`
- Test: `tests/test_calendar_bridge.py`

**Interfaces:**
- Consumes: `CalendarBridge.calendar_status() -> tuple[bool, str]`
- Produces: updated doctor output and user-facing docs for iCloud-only sync

- [ ] **Step 1: Write the failing tests**

```python
def test_run_doctor_reports_icloud_target(monkeypatch, capsys):
    monkeypatch.setattr("mplan.doctor.default_data_dir", lambda: "/tmp/.mplan")
    monkeypatch.setattr("mplan.doctor.default_db_path", lambda: "/tmp/.mplan/mplan.db")
    monkeypatch.setattr("mplan.doctor.CalendarBridge", lambda: type("Bridge", (), {
        "healthcheck": lambda self: (True, "Calendar automation available"),
        "calendar_status": lambda self: (True, "iCloud::mplan"),
    })())

    assert run_doctor() == 0
    out = capsys.readouterr().out
    assert "Target calendar: iCloud::mplan" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/bin/pytest tests/test_cli.py::test_main_returns_zero_for_doctor tests/test_calendar_bridge.py::test_run_doctor_reports_icloud_target -q`
Expected: FAIL because `run_doctor()` does not print target calendar information

- [ ] **Step 3: Write minimal implementation**

```python
def run_doctor() -> int:
    bridge = CalendarBridge()
    ok, detail = bridge.healthcheck()
    target_ok, target_detail = bridge.calendar_status()
    print(f"Data dir: {default_data_dir()}")
    print(f"Database: {default_db_path()}")
    print("Calendar:", "ok" if ok else "error")
    print(detail)
    print("Target calendar:", target_detail if target_ok else f"error: {target_detail}")
    return 0 if ok and target_ok else 1
```

- [ ] **Step 4: Update README for iCloud-only sync**

```markdown
## Sync Behavior

- `mplan` writes owned planner events into `iCloud > mplan`
- if the `mplan` calendar does not exist under iCloud, `mplan` creates it automatically
- older `mplan` events created in a local Mac calendar are migrated into iCloud during later syncs
- if iCloud Calendar is unavailable, sync fails instead of falling back to a local-only calendar
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src ./.venv/bin/pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mplan/doctor.py README.md tests/test_cli.py tests/test_calendar_bridge.py
git commit -m "docs: describe icloud calendar sync"
```

## Self-Review

- Spec coverage:
  - iCloud-only target selection is covered by Task 1
  - automatic creation of `iCloud > mplan` is covered by Task 1
  - migration of previously owned local-calendar events is covered by Task 2
  - preserving `external_event_id`-based updates is covered by Task 2
  - doctor visibility and user-facing guidance are covered by Task 3
- Placeholder scan:
  - no `TODO`, `TBD`, or “handle appropriately” placeholders remain
- Type consistency:
  - `CalendarBridge.ensure_target_calendar() -> str`
  - `CalendarBridge.calendar_status() -> tuple[bool, str]`
  - `CalendarBridge.upsert_owned_event(...) -> tuple[str, str | None]`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-10-mplan-icloud-calendar-implementation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
