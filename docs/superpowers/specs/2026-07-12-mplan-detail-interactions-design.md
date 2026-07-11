# mplan Detail Interactions Design

## Goal

Make the month-grid and detail overlay internally consistent: overflow uses a neutral ellipsis, one arrow-key press moves once, local tasks can be completed or deleted from the detail overlay, and the overlay border remains aligned for mixed-width text.

## Interaction Design

- An overflowing day cell ends with `...` only. It does not advertise the removed `v DD` workflow or repeat the globally documented Enter shortcut.
- In normal mode, one Left or Right key sequence moves the selected day exactly once. Up and Down continue moving by one week.
- Enter opens the selected day's detail overlay. Within the overlay:
  - Up and Down move through local mplan tasks across the morning, afternoon, and evening buckets.
  - Space toggles the selected task's completed state.
  - `d` deletes the selected task.
  - Esc closes the overlay.
- Imported calendar events are displayed but cannot be selected, completed, or deleted.
- The status line changes while the overlay is open so these controls are discoverable.

## Delete Consistency

Deletion distinguishes imported calendar events from events owned by mplan.

- A local task without an `external_event_id` is deleted from SQLite immediately.
- A local task with an `external_event_id` first asks the calendar bridge to delete that exact event from the writable `mplan` calendar. Only after that succeeds is the SQLite row deleted.
- If calendar deletion fails, the local task remains and the overlay reports the error. This avoids losing the identifier required to retry and prevents orphaned calendar events.
- Events merely imported from other calendars are never passed to the delete path.

## Rendering

All detail-panel fitting and padding uses terminal display width rather than Python character count. Full-width CJK characters count as two columns, combining characters as zero, and ordinary characters as one. Every rendered panel row therefore has the same display width and the right border stays fixed.

Completed tasks use the existing `✓ ` prefix in both the grid and detail overlay. The selected local task receives a visible cursor marker without changing panel width.

## Key Parsing

Escape-sequence parsing consumes a complete CSI or SS3 arrow sequence during one read operation and returns exactly one logical command. Partial-sequence state is not allowed to leak into the next application loop iteration. Tests cover CSI, SS3, and parameterized sequences.

## Verification

Automated tests cover:

- neutral overflow ellipsis;
- single-read arrow decoding and single-step date movement;
- detail selection bounds and movement;
- completion toggling;
- unsynced task deletion;
- synced task deletion ordering and failure preservation;
- imported-event protection;
- display-width alignment for Chinese and mixed-width content;
- status-line shortcut text.

The full test suite, package build/install path, `mplan --help`, and a clean invocation using the globally resolved `mplan` executable are checked before publishing.
