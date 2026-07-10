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
