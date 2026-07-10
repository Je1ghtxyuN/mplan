# Task 1 Report: iCloud Target Calendar Resolution

## Implemented

- Added `CalendarBridge.TARGET_CALENDAR_NAME = "mplan"`.
- Added `CalendarBridge.ensure_target_calendar()` to resolve a dedicated iCloud calendar named `mplan`.
- The AppleScript now:
  - scans writable calendars for an existing iCloud calendar named `mplan`,
  - returns `iCloud::mplan` when it exists,
  - creates the calendar in the iCloud container when it does not exist,
  - raises a clear error if no iCloud calendar source is available.
- Added `CalendarBridge.calendar_status()` so status reporting goes through the target-calendar resolver and returns `(bool, detail)`.

## Tested

- Red phase:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_ensure_target_calendar_uses_existing_icloud_mplan tests/test_calendar_bridge.py::test_calendar_status_reports_icloud_target -q`
  - Result: failed with `AttributeError` for missing `ensure_target_calendar` and `calendar_status`.
- Green phase:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_ensure_target_calendar_uses_existing_icloud_mplan tests/test_calendar_bridge.py::test_calendar_status_reports_icloud_target -q`
  - Result: `2 passed`
- Regression check:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py -q`
  - Result: `7 passed`

## TDD Evidence

- RED: the two new tests failed before implementation because the methods did not exist.
- GREEN: after implementing the resolver and status wrapper, the targeted tests passed.
- The full `tests/test_calendar_bridge.py` file also passed after the change.

## Files Changed

- `src/mplan/calendar_bridge.py`
- `tests/test_calendar_bridge.py`
- `.superpowers/sdd/task-1-icloud-report.md`

## Self-Review / Concerns

- AppleScript `container` handling in Calendar.app can be a little platform-specific, so the `iCloud` source detection should be manually verified on a real Mac if behavior looks off.
- The task brief’s example test stubs had contradictory return values, so I normalized the test fixtures to reflect the intended `iCloud::mplan` contract.
- Migration of existing events was intentionally not touched in this task.

## Follow-up Fix: Event Upsert Targeting

### Implemented

- Wired the iCloud target-calendar resolution into `upsert_owned_event()` so new owned events no longer create in `item 1 of writableCalendars`.
- New events now resolve or create the dedicated iCloud `mplan` calendar before creation.
- Existing event updates still search by `uid` across calendars, which keeps the current return type and avoids Task 2 migration semantics.

### Additional Coverage Added

- `test_upsert_owned_event_targets_icloud_mplan_calendar`
  - Proves the upsert script now contains the iCloud target-calendar resolver.
  - Proves the old `item 1 of writableCalendars` path is gone.
- `test_ensure_target_calendar_creates_icloud_mplan_when_missing`
  - Proves the create-when-missing branch is present in the generated AppleScript.
- `test_calendar_status_reports_no_writable_icloud_failure`
  - Proves the failure path is surfaced through `calendar_status()` when the target resolution fails.

### Tested

- Red phase:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_owned_event_targets_icloud_mplan_calendar -q`
  - Result: failed because `upsert_owned_event()` still used the first writable calendar.
- Green phase:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_owned_event_targets_icloud_mplan_calendar -q`
  - Result: `1 passed`
- Regression check:
  - `PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py -q`
  - Result: `10 passed`

### Self-Review / Concerns

- The iCloud calendar source detection is still AppleScript-driven and depends on Calendar.app container naming, so it should be kept under watch on macOS.
- I intentionally did not change the owned-event return type or add migration behavior; that remains reserved for Task 2.
