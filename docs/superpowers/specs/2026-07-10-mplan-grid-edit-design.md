# mplan Grid Edit Design

## Goal

Keep the existing month-grid terminal planner as the default interface and add Vim-like keyboard editing on top of it, without replacing the current grid layout with a separate full-screen TUI.

## Scope

This design covers:

- Keeping the existing month-grid rendering in `src/mplan/app.py` as the default interactive UI
- Adding keyboard-driven navigation with arrow keys for day selection
- Adding bucket selection with `Tab` across `早 / 午 / 晚`
- Adding `NORMAL` and `INSERT` modes
- Editing the selected bucket through a single-line bottom editor bar
- Saving locally on `Esc` and syncing explicitly on `s`
- Preserving the existing month-grid appearance as much as possible

This design does not cover:

- Replacing the default UI with the new `src/mplan/tui.py` runtime
- Editing individual items as separate cursor targets
- Multi-line editor behavior
- Mouse support
- A GUI outside the terminal

## User Experience

### Layout

The existing month grid remains the main screen.

The screen has two regions:

- Main month grid, preserving the current cell-based display
- Bottom status/editor bar, styled like a simple nvim statusline

The grid remains the focus of the app. The bottom bar is only for status and single-line editing, not the primary content view.

### Selection Model

The app tracks:

- Visible month
- Selected day
- Selected bucket in the selected day
- Current mode

The editable unit is `selected day + selected bucket`.

### Modes

Two modes only:

- `NORMAL`
- `INSERT`

The app starts in `NORMAL`.

### Normal Mode Keys

- `↑ ↓ ← →`: move selected day
- `Tab`: cycle selected bucket through `早 -> 午 -> 晚 -> 早`
- `i`: enter `INSERT` mode for the selected bucket
- `s`: sync visible month
- `q`: quit

The old prompt commands like `e DD` and `v DD` are no longer the primary interaction path in the default interface once this design is implemented.

### Insert Mode Keys

- Printable input edits the current bucket text
- Backspace deletes backward
- `Esc`: save current bucket locally and return to `NORMAL`

The insert buffer is single-line only in v1.

### Editing Behavior

The bottom bar shows the currently selected day and bucket plus the editable buffer.

Example shape:

- `NORMAL | 2026-07-10 | 午 | Tab切分区 i编辑 s同步 q退出`
- `INSERT | 2026-07-10 | 午 | 改简历 | Esc保存`

The selected bucket’s current text is loaded into the editor when entering `INSERT`.

### Bucket Semantics

Bucket content is still stored as multiple planner items.

For editing:

- Existing bucket content is joined with ` | `
- On save, the edited line is split by `|`
- Empty chunks are dropped
- The target bucket is replaced with the parsed items

## Visual Direction

The goal is “nvim-like” in feel, not a literal Neovim clone.

That means:

- Strong selected-day highlight in the grid
- Stronger selected-bucket emphasis inside the selected day cell
- Bottom statusline/editor bar with compact, mode-first text
- No gray full-screen overlay effect from the alternate full-screen TUI

The month grid itself remains visually recognizable as the existing planner.

## Architecture

### Default Runtime

Keep `src/mplan/app.py` as the default interactive runtime launched by `mplan`.

`src/mplan/cli.py` should route `launch_app()` to `run_app()` rather than the alternate full-screen runtime.

### New Responsibility Split

The grid app should gain a light interaction layer rather than being replaced.

Recommended additions:

- Extend `src/mplan/app.py` with mode, selected bucket, and editor buffer state
- Add small pure helpers for:
  - bucket cycling
  - buffer serialization/parsing
  - statusline text generation
  - movement across the existing month grid

If extraction becomes useful, a small helper module is acceptable, but the design should stay centered on the existing grid app rather than a second runtime stack.

### Existing Components to Reuse

- `src/mplan/month_grid.py` for month topology and cell rendering
- `src/mplan/storage.py` for persistence
- `src/mplan/sync.py` for explicit sync
- `src/mplan/day_editor.py` bucket parsing ideas, but not necessarily its prompt flow

## Rendering Rules

### Grid Preservation

The current grid stays visible and remains the primary display.

Do not degrade the default display into:

- day-number-only rows
- selected-day-only detail output
- a non-grid full-screen TUI as the main experience

### Selected Day

The selected day should remain visibly highlighted in the month grid.

### Selected Bucket

Inside the selected day cell, the active bucket should be distinguishable from the other two buckets.

This can be done with a simple label marker in v1, for example:

- `>早:`
- `>午:`
- `>晚:`

or another equally compact emphasis that preserves the grid layout.

### Bottom Bar

The bottom bar must always remain visible.

The body rendering must reserve space for:

- one status/editor line

If the terminal is short, trim the grid/body content before losing the bottom bar.

## Data and Save Behavior

### Enter Insert

On `i`:

- Load current bucket text
- Join items with ` | `
- Put the result into the editor buffer
- Switch to `INSERT`

### Exit Insert

On `Esc`:

- Parse the current line by `|`
- Replace the selected day + bucket contents in storage
- Set a short status message like `已保存`
- Return to `NORMAL`

No sync happens automatically on save.

### Sync

On `s` in `NORMAL`:

- Sync visible month
- Show sync result or warning in the bottom bar

## Testing Strategy

Add or update tests for:

- CLI launches the grid runtime by default
- Arrow-key day movement logic
- `Tab` bucket cycling
- `i` loads the selected bucket into the editor buffer
- `Esc` saves and returns to `NORMAL`
- Bottom bar remains visible when content is long
- Selected bucket highlighting is present in the grid render
- Existing month-grid content still appears for visible days

## Acceptance Criteria

This design is successful when:

- Running `mplan` opens the original month-grid-based interface, not the alternate full-screen TUI
- The user can move between dates with arrow keys
- The user can switch `早 / 午 / 晚` with `Tab`
- Pressing `i` opens a single-line editor in the bottom bar for the selected bucket
- Pressing `Esc` saves that bucket and returns to `NORMAL`
- The month grid remains the main visual structure
- The bottom bar stays visible for status and editing
- `s` remains the explicit sync trigger
