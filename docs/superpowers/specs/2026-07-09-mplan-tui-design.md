# mplan Vim-like TUI Design

## Goal

Replace the current line-oriented `input()` month app with a full-screen terminal UI that feels closer to Vim-style editing while preserving the existing SQLite storage model and Calendar sync behavior.

## Scope

This design covers:

- Replacing the current `run_app()` loop with a persistent TUI event loop
- Introducing a modal interaction model with `NORMAL` and `INSERT` modes
- Making the selection unit `day + bucket` where `bucket` is one of `早`, `午`, or `晚`
- Editing planner content through an in-memory buffer and saving on `Esc`
- Keeping Calendar sync explicit on `s` instead of auto-syncing on every edit
- Reusing existing storage and sync layers wherever possible

This design does not cover:

- Direct manipulation of individual planner items as separate cursor targets
- A Vim command-line layer such as `:w`, `:q`, `dd`, or macro support
- Mouse support
- A graphical UI outside the terminal

## Current Project Context

The current app has two terminal-facing entry points:

- `mplan add/done/sync/doctor` in `src/mplan/cli.py`
- A printed month grid plus command prompt flow in `src/mplan/app.py`

The storage model is already a good fit for bucket-level editing:

- Planner records are stored as `PlannerItem(day, bucket, text, completed, ...)`
- Buckets are fixed to `早`, `午`, `晚`
- The existing day editor already treats each bucket as a grouped editing surface

The main mismatch today is interaction style, not data shape. The current UI redraws the month and blocks on `input()`, which prevents arrow-key navigation, continuous focus, or an insert-mode editing flow.

## User Experience

### Modes

The TUI has exactly two modes:

- `NORMAL`: navigation and commands
- `INSERT`: text entry into the selected bucket

The app starts in `NORMAL`.

### Selection Model

At all times the app tracks:

- The visible month
- The selected day
- The selected bucket within that day
- The current mode

The cursor target is always a specific `day + bucket` pair. This is the smallest editable unit in the first version.

### Keybindings

#### NORMAL mode

- Arrow keys: move between day cells
- `Tab`: cycle selected bucket in the current day through `早 -> 午 -> 晚 -> 早`
- `Shift-Tab` if supported by the terminal: cycle backward; otherwise it is optional and not required for the first version
- `i`: enter `INSERT` mode for the selected `day + bucket`
- `s`: sync the currently visible month with Calendar
- `q`: quit the app

The first version intentionally does not assign completion toggling, deletion shortcuts, or Vim-style text objects. Those can be layered on later after the edit flow is stable.

#### INSERT mode

- Printable text input appends to the edit buffer
- Backspace deletes backward
- Left and right arrow keys move within the line if supported by the editing implementation
- `Esc`: save the current buffer into the selected bucket, leave `INSERT`, return to `NORMAL`

The first version uses a single-line logical buffer for the selected bucket. Multiple planner entries are represented by `|` separators inside that buffer.

### Save and Sync Semantics

Pressing `Esc` in `INSERT` mode:

1. Parses the buffer by `|`
2. Trims empty segments
3. Replaces the planner items for the selected `day + bucket`
4. Persists those changes to SQLite immediately
5. Returns to `NORMAL`

Pressing `Esc` does not trigger Calendar sync.

Pressing `s` in `NORMAL` mode:

1. Runs the existing month sync for the visible month
2. Shows the sync result in the status area
3. Leaves local edits intact

This separation keeps editing responsive and avoids a slow or failure-prone external sync on every edit exit.

## Screen Layout

### Main Layout

The full-screen TUI is split into three regions:

1. Header
2. Month grid
3. Footer area

### Header

The header shows:

- Current year and month
- Current mode
- Optional transient status such as sync success or validation messages

### Month Grid

The center of the screen remains a seven-column month grid.

Each cell shows:

- Day number
- Imported Calendar events
- `早`
- `午`
- `晚`

Visual emphasis distinguishes:

- The selected day
- The selected bucket within that day
- Days outside the visible month

The selection rules are:

- Selected day: whole cell gets a visible highlight
- Selected bucket: that bucket row inside the selected day gets a stronger highlight

This allows the user to understand both location and exact edit target at a glance.

### Footer

The footer serves two roles:

- In `NORMAL`, it is a status bar showing current date, current bucket, and key hints
- In `INSERT`, it additionally shows the editable buffer for the selected bucket

The editing surface lives in the footer rather than directly inside the day cell. This keeps the grid readable and avoids forcing a cramped inline text editor into a tiny calendar box.

## Data Model and Persistence

### Existing Model Reuse

No database schema changes are required for the first version.

The TUI continues to use:

- `Store.list_days_in_month()`
- `Store.list_day_items()`
- `Store.delete_day_bucket()`
- `Store.upsert_planner_item()`
- Existing imported event reads from the sync layer

### Bucket Serialization

For display and editing, a bucket is serialized as:

- Planner texts joined by ` | `

For save, the input buffer is deserialized as:

- Split on `|`
- Trim whitespace on each segment
- Drop empty segments
- Replace the bucket contents in storage

If the resulting segment list is empty, the bucket is cleared.

### Completion State

The first version does not expose per-item completion editing in the TUI.

Because a bucket edit replaces the bucket contents as a flat text list, existing completion state in that bucket is discarded on save. This is acceptable for the first version because the chosen interaction model edits at bucket granularity rather than item granularity.

This tradeoff should be documented in user-facing notes once implementation begins.

## Architecture

### New TUI Layer

Introduce a dedicated TUI module instead of continuing to expand `src/mplan/app.py` as a prompt-driven loop.

Recommended file structure:

- `src/mplan/tui.py`
  - Top-level curses application loop
  - Screen drawing orchestration
  - Keyboard event dispatch
- `src/mplan/tui_state.py`
  - Immutable or minimally mutable state container for month, selection, mode, status, and edit buffer
  - Pure transition helpers for movement and mode changes
- `src/mplan/tui_render.py`
  - Pure rendering helpers that convert state plus store data into screen lines or cell models

The existing `src/mplan/month_grid.py` can continue to provide month topology and text wrapping behavior, but it will likely need small extensions to represent selected bucket state separately from selected day state.

### App Entry

`src/mplan/cli.py` should continue to launch the interactive app when no subcommand is provided. Internally, `launch_app()` should call the new TUI entrypoint instead of the current prompt loop.

### State Responsibilities

The TUI state should own:

- `visible_month`
- `selected_day`
- `selected_bucket`
- `mode`
- `edit_buffer`
- `status_message`

The persistence layer should remain unaware of cursor state, modes, or rendering concerns.

## Navigation Rules

### Day Movement

Arrow key movement should follow the month grid coordinates rather than day arithmetic:

- Left and right move within the week row
- Up and down move by week

If movement lands on an adjacent-month cell:

- Allow selecting that cell immediately
- If the selected day belongs to another month, immediately switch the visible month to that day’s month
- Rebuild the grid with the newly selected day preserved

This immediate month-follow behavior is the required first-version rule because it matches user expectation and avoids hidden intermediate selection state.

### Bucket Movement

`Tab` cycles buckets in a fixed order:

- `早`
- `午`
- `晚`

The bucket selection is sticky across day movement. If the user is on `午` and moves to another day, the selected bucket remains `午`.

## Error Handling

The TUI should not crash on:

- Empty buckets
- Empty months with no planner data
- Sync warnings
- Terminal size too small for the preferred grid layout

If the terminal is too small, the app should either:

- Fall back to a compact month rendering inside the TUI, or
- Show a clear resize message and keep running

The first implementation can choose the simpler of those two behaviors, but the behavior must be explicit and testable.

## Testing Strategy

The implementation should avoid putting complex logic directly into curses callbacks. Most logic should be extracted into pure functions so tests do not depend on a live terminal.

### Unit tests

Add tests for:

- Bucket cycling
- Day movement across week and month boundaries
- Entering and leaving `INSERT`
- Buffer serialization and deserialization
- Saving an edited bucket into storage
- Preserving selected bucket when moving between days

### Rendering tests

Add tests for:

- Selected day highlight metadata
- Selected bucket highlight metadata
- Footer content in `NORMAL`
- Footer content in `INSERT`
- Small terminal fallback behavior

### Integration smoke test

If practical, add a minimal smoke test for the TUI entrypoint that verifies the app can initialize state and invoke the main loop wrapper without requiring a real interactive session.

## Migration Notes

The current `edit_day()` prompt-based editor can remain in the repository during the transition, but it should stop being the primary interactive path once the new TUI launches by default.

The CLI subcommands `add`, `done`, `sync`, and `doctor` remain supported unchanged.

## Open Tradeoffs Chosen Deliberately

### Why edit the bucket in the footer instead of inline in the cell

Inline editing inside a month cell sounds closer to a spreadsheet, but in practice the cell is too small and the rendering logic becomes much more fragile. The footer editor keeps the grid readable while still making the selected cell the focus target.

### Why save on `Esc` but sync on `s`

This gives the user the immediate confidence that local edits are durable, without tying every insert-mode exit to Apple Calendar automation or network-like delays in the sync layer.

### Why skip per-item cursoring in version one

The existing persistence model and current UI both already group work by bucket. Bucket-level editing is the smallest useful step that delivers the desired “move, press `i`, type, press `Esc`” workflow without inventing a much more complicated nested selection system.

## Acceptance Criteria

The design is successful when all of the following are true:

- Launching `mplan` opens a full-screen terminal UI instead of a prompt loop
- The user can move across the calendar with arrow keys
- The user can switch between `早`, `午`, and `晚` within the selected day
- Pressing `i` opens an insert flow for the selected bucket
- Pressing `Esc` saves the edited bucket locally and returns to `NORMAL`
- Pressing `s` syncs the visible month
- The implementation reuses the current storage and sync stack instead of replacing it
- The core state and rendering logic are covered by automated tests
