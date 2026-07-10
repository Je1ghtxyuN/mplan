# Task 2: Migrate Old Owned Events Into iCloud

## Summary

Implemented Task 2 in the allowed file set:

- `src/mplan/calendar_bridge.py`
- `src/mplan/sync.py`
- `tests/test_calendar_bridge.py`
- `tests/test_sync.py`

The bridge now supports the Task 2 migration contract for owned events:

- If `external_event_id` resolves inside `iCloud > mplan`, update that event in place.
- If `external_event_id` resolves to a non-iCloud event whose notes identify `{"source": "mplan"}`, create the equivalent event in `iCloud > mplan`, return the new iCloud UID, and delete the old owned event.
- Otherwise, create a new event in `iCloud > mplan` and leave unrelated user events untouched.

`SyncEngine.push_day()` now consumes the new bridge return type and persists only the new iCloud UID back into `external_event_id`.

## TDD Log

### Red

Added the failing tests requested in the brief:

- `tests/test_calendar_bridge.py::test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration`
- `tests/test_sync.py::test_sync_month_updates_external_event_id_after_migration`

Ran:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration tests/test_sync.py::test_sync_month_updates_external_event_id_after_migration -q
```

Observed expected failures:

- `CalendarBridge.upsert_owned_event()` still returned a bare string instead of `(event_id, deleted_event_id)`
- `SyncEngine.push_day()` stored the whole return value instead of only the new iCloud UID

### Green

Implemented the minimal production changes:

- changed `CalendarBridge.upsert_owned_event()` to return `tuple[str, str | None]`
- returned AppleScript JSON payload with `event_id` and `deleted_event_id`
- added migration-only deletion path guarded by `source: "mplan"` metadata
- updated `SyncEngine.push_day()` to persist only `event_id`

### Refactor / Test Alignment

Adjusted existing bridge tests to use the new JSON stub payloads and updated assertions to match the new migration guard flow.

## Verification

Targeted red/green command:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration tests/test_sync.py::test_sync_month_updates_external_event_id_after_migration -q
```

Result:

- `2 passed`

Full task-local verification:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py tests/test_sync.py -q
```

Result:

- `23 passed`

## Self-Review

Checked the implementation against the brief:

- migration is only permitted in Task 2 and is implemented only in `upsert_owned_event()`
- deletion is only reached when the old event notes identify `source: "mplan"`
- unrelated non-iCloud events are never deleted
- the new iCloud UID is written back through `attach_external_event_id()`
- Task 1 safety remains in place because writes still resolve through the dedicated writable `iCloud > mplan` calendar block

## Commit

Planned commit message:

```bash
feat: migrate owned calendar events to icloud
```

## Notes / Concerns

No blocking issues found.

One conservative behavior is worth noting: the AppleScript ownership check looks for the `source: "mplan"` marker in the event notes string rather than attempting broader JSON parsing in AppleScript. That keeps the migration path biased toward false negatives instead of false positives, which is safer for the brief’s “never migrate or delete unrelated user events” constraint.

## Fix Pass

Addressed the follow-up findings inside the same owned file set.

### Finding 1: Off-target migration safety

Root cause:

- `CalendarBridge.upsert_owned_event()` treated any off-target event with `source: "mplan"` metadata as migratable.
- That allowed read-only/subscribed/imported matches to fall into the delete-after-copy path.

Fix:

- tightened the AppleScript migration branch so an off-target event is only eligible for migration when both conditions are true:
  - its notes identify `source: "mplan"`
  - its source calendar is writable
- read-only/subscribed/imported matches now fall through to “create fresh event in `iCloud > mplan`” without deleting the original event

Added focused regression coverage:

- `tests/test_calendar_bridge.py::test_upsert_only_migrates_owned_events_from_writable_source_calendars`

### Finding 2: `pull_month()` contract regression

Root cause:

- `SyncEngine.pull_month()` had been changed to return only cached imported events from the store.
- existing render callers still depend on `pull_month()` doing a live bridge fetch and filtering owned events

Fix:

- restored `pull_month()` to its original live-fetch contract using `bridge.list_timed_events(...)`
- kept `refresh_month_imports()` cache fallback behavior by reading cached store imports directly on fetch failure, instead of routing through `pull_month()`

Added focused regression coverage:

- `tests/test_sync.py::test_pull_month_uses_live_bridge_fetch_and_filters_owned_imports`

### Fix Verification

Targeted fix-pass regression command:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py::test_upsert_only_migrates_owned_events_from_writable_source_calendars tests/test_sync.py::test_pull_month_uses_live_bridge_fetch_and_filters_owned_imports -q
```

Result:

- `2 passed`

Full owned-suite verification:

```bash
PYTHONPATH=src ./.venv/bin/pytest tests/test_calendar_bridge.py tests/test_sync.py -q
```

Result:

- `25 passed`
