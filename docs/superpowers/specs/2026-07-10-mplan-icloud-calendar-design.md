# mplan iCloud Calendar Sync Design

## Goal

Make `mplan` sync planner tasks into a dedicated iCloud calendar so events created on macOS are also visible on iPhone and iPad through iCloud Calendar sync.

The target behavior is:

- `mplan` never writes planner events into an arbitrary writable calendar
- `mplan` uses a dedicated iCloud calendar named `mplan`
- if that calendar does not exist, `mplan` creates it automatically under the user's iCloud calendars
- if no writable iCloud calendar/account is available, `mplan` fails with a clear error instead of silently writing to `On My Mac`

## Why Change

Today `CalendarBridge.upsert_owned_event()` selects the first writable calendar in Calendar.app. That is unreliable because Calendar.app can expose multiple writable calendars at once, including:

- local `On My Mac` calendars
- Google or Exchange calendars
- multiple iCloud calendars

This makes sync nondeterministic. A planner event can appear on the Mac but never reach iPhone or iPad if it lands in a local-only calendar.

## Design Summary

`mplan` will adopt a single-target calendar policy:

- target account type: iCloud only
- target calendar name: `mplan`
- target calendar creation: automatic, if missing
- fallback behavior: none

This is intentionally strict. The product promise becomes: if sync succeeds, the event is in the dedicated iCloud calendar.

## Calendar Selection Model

### Required Behavior

When `mplan` needs to create or update an owned event, it will:

1. inspect Calendar.app calendars
2. find a writable iCloud calendar named `mplan`
3. if found, use it
4. if not found, create a new writable iCloud calendar named `mplan`
5. if iCloud calendars are unavailable or not writable, raise a user-facing error

### iCloud Detection

Apple Calendar exposes both calendar names and container/source information through AppleScript. The implementation must identify calendars whose backing account/source is iCloud rather than relying on ordering.

The selector must reject:

- `On My Mac`
- subscribed read-only calendars
- non-iCloud writable calendars

If multiple iCloud calendars named `mplan` somehow exist, `mplan` should use the first exact match returned by Calendar.app and surface a warning-capable path later if we want extra diagnostics. For this scope, deterministic first exact match is sufficient.

## Calendar Creation Model

If no iCloud calendar named `mplan` exists, `mplan` will create one inside the writable iCloud source/account.

Creation requirements:

- create calendar with exact name `mplan`
- create it only under an iCloud source/account
- never create a fallback local calendar
- fail clearly if iCloud source exists but is not writable

The design assumes Calendar.app can create calendars via AppleScript for a writable iCloud source. If Calendar automation returns an operational error during creation, that error should be surfaced in a friendly message.

## Event Ownership, Migration, and Update Semantics

Existing event ownership rules remain in place:

- `mplan` embeds JSON metadata in event notes
- metadata continues to include `source: "mplan"` and `item_id`
- `external_event_id` remains the stable link between local planner items and Calendar events

This means the new calendar-targeting behavior changes where owned events live, but does not change how task updates are tracked.

Update/delete rules:

- create new planner item: create event in `iCloud > mplan`
- update planner item: update the existing linked event if `external_event_id` resolves
- delete linked item/event path: only delete the owned event identified by `external_event_id`

### Migration of Older Local Events

Some existing `mplan` events may already live in a local or non-iCloud calendar because older versions wrote to the first writable calendar.

The new behavior should migrate those historical owned events forward into `iCloud > mplan` rather than leaving them stranded.

Migration rules:

- if `external_event_id` resolves to an owned event already inside `iCloud > mplan`, update it in place
- if `external_event_id` resolves to an owned event in a non-iCloud calendar, `mplan` should create or update the equivalent event inside `iCloud > mplan`, store the new iCloud event UID back into `external_event_id`, and then delete the old non-iCloud owned event
- if `external_event_id` does not resolve anywhere, create a fresh owned event in `iCloud > mplan`

This gives users a one-way convergence path: after enough syncs, all surviving `mplan` events end up inside the dedicated iCloud calendar.

Safety constraints:

- only migrate events whose metadata identifies them as `source: "mplan"`
- never delete or rewrite unrelated user events
- never migrate non-owned events imported from other calendars

New event creation must always target `iCloud > mplan`.

## User-Facing Behavior

### Sync Success

On successful sync, behavior is unchanged except events now reliably appear in the iCloud-backed `mplan` calendar and therefore replicate to other Apple devices signed into the same iCloud account with Calendar enabled.

### Sync Failure

If no writable iCloud calendar/account is available, users should get an explicit message such as:

`未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步`

If calendar creation fails:

`无法创建 iCloud 日历 mplan: <system error>`

### Doctor Output

`mplan doctor` should report:

- database path
- Calendar automation availability
- target sync calendar policy: `iCloud > mplan`
- whether a writable iCloud source is currently detectable

This gives users an easy way to verify whether cross-device sync is expected to work.

## Backward Compatibility

This change is intentionally stricter than the current behavior.

Compatibility expectations:

- existing local planner data remains unchanged
- existing linked external event IDs remain usable
- future syncs stop creating new events in arbitrary writable calendars
- older owned events in local calendars are progressively moved into `iCloud > mplan`
- users without iCloud Calendar configured will now receive a hard failure rather than a silent local-only success

That last point is desirable because it aligns runtime behavior with the user expectation of “sync to iCloud”.

## Error Handling

The implementation should distinguish:

1. Calendar automation unavailable
2. iCloud source unavailable
3. iCloud source available but not writable
4. target calendar lookup failed
5. target calendar creation failed

These conditions should collapse into concise user-facing messages, but the internal bridge code should keep them separate enough for diagnosis and tests.

## Testing Strategy

Add or update tests around:

- selecting only iCloud calendars rather than the first writable calendar
- generating AppleScript that targets the `mplan` iCloud calendar
- automatic creation when target calendar is missing
- clear failure when no writable iCloud source exists
- migration of previously owned local-calendar events into the iCloud target calendar
- `doctor` reporting the iCloud target policy

Regression coverage should preserve:

- existing owned-event metadata format
- existing event update-by-UID behavior
- no fallback to arbitrary writable local calendars

## Out of Scope

These are intentionally excluded from this design:

- user-configurable custom calendar names
- choosing among multiple iCloud calendars interactively
- syncing to Google/Exchange calendars
- two-way editing from Calendar.app back into planner items

Those can be future enhancements if needed, but they are not required for the best default iCloud experience.
