# mplan Command Mode Design

## Goal

Refine the current grid-based `mplan` TUI so it behaves more like `nvim`: `NORMAL` is for selection only, `INSERT` is for focused task entry/editing, `COMMAND` is for actions entered with `:`, and day details open in a centered expanded view rather than being squeezed into the bottom line.

## Scope

This design covers:

- Keeping the existing month grid as the main display
- Restricting `NORMAL` mode to navigation and bucket selection
- Adding a bottom `COMMAND` mode entered with `:`
- Supporting both short and long command aliases
- Adding `:sq` as sync-and-quit
- Replacing the old prompt-style `v DD` / `e DD` interaction in the TUI with commands targeting the currently selected day
- Adding a centered day-detail view that expands the full selected day while visually dimming the month grid behind it
- Making `i` create a new task in the active bucket instead of rewriting the whole bucket line
- Styling the bottom statusline with distinct mode colors and a more `nvim`-like feel

This design does not cover:

- Replacing the grid UI with a separate full-screen runtime
- Multi-line editing
- Mouse support
- Arbitrary ex-command syntax or ranges
- Shell escapes or nested prompts

## User Experience

### Layout

The existing month grid remains the dominant screen region in `NORMAL`.

The bottom line becomes a real mode-aware statusline:

- Left: colored mode label
- Middle: command input or status text
- Right: selected date and bucket

The bottom line is always visible, even when the terminal is short.

When the user opens details for a day, a centered modal-like detail panel appears over the grid:

- the background month grid remains faintly visible
- the detail panel shows the full selected day
- the active bucket stays highlighted inside the panel
- `Esc` dismisses the panel and returns to the month grid

### Modes

The app has exactly three modes:

- `NORMAL`
- `INSERT`
- `COMMAND`

The app starts in `NORMAL`.

Separately from these modes, the app may show a day-detail overlay. The overlay is a view state, not a fourth editing mode.

### Normal Mode

`NORMAL` is for choosing context only. It should not directly run sync, quit, or detail actions.

Allowed keys:

- `← ↑ ↓ →`: move selected day
- `Tab`: cycle `早 -> 午 -> 晚 -> 早`
- `i`: create a new task in the active bucket
- `Enter`: open the day-detail overlay
- `:`: enter `COMMAND`

Disallowed direct actions in `NORMAL`:

- direct sync
- direct quit
- direct detail view
- direct month jump through old prompt commands

This keeps `NORMAL` clean and predictable.

### Insert Mode

`INSERT` edits one concrete task entry at a time.

Allowed behavior:

- printable input edits the single-line buffer for the current task draft or selected task
- backspace deletes backward
- `Esc` saves locally and returns to the previous non-insert state

`INSERT` does not run commands.

### Day-Detail Overlay

The day-detail overlay expands the selected day in the center of the screen.

It shows:

- selected day header
- imported calendar events for that day
- all `早 / 午 / 晚` tasks for that day
- visible highlight for the currently active bucket

Behavior:

- entered with `Enter` in `NORMAL`
- also entered with `:v` or `:view`
- `Tab` can continue to switch the active bucket while the overlay is open
- `i` while the overlay is open creates a new task in the active bucket
- `Esc` closes the overlay

The overlay is primarily a richer reading and task-management surface, not a replacement for the month grid.

### Command Mode

`COMMAND` is entered by typing `:`.

The statusline becomes a command prompt similar to a light `vim` command line.

Behavior:

- printable input edits the command buffer
- backspace deletes backward
- `Enter` executes the command
- `Esc` cancels command input and returns to `NORMAL`

Command execution targets the currently selected day and currently visible month.

## Command Set

### Alias Strategy

Commands should support both short and long forms.

Short forms are the primary UX. Long forms are compatibility and readability aliases.

Recommended aliases:

- `:q` / `:quit`
- `:s` / `:sync`
- `:sq` / `:syncquit`
- `:v` / `:view`
- `:n` / `:next`
- `:p` / `:prev`

### Semantics

- `:q` / `:quit`
  - exit the app
- `:s` / `:sync`
  - sync the visible month and remain in the app
- `:sq` / `:syncquit`
  - sync the visible month, then exit if sync completed without raising an error
- `:v` / `:view`
  - open the centered day-detail overlay for the currently selected day
- `:n` / `:next`
  - move visible month forward and select the first day of that month
- `:p` / `:prev`
  - move visible month backward and select the first day of that month

Unknown commands should not crash the app. They should return to `NORMAL` with a short status like `未知命令: xyz`.

## Migration of Old TUI Commands

The old prompt-style TUI commands such as `v DD` and `e DD` should no longer be part of the interactive bottom workflow.

In the new TUI:

- `:v` replaces `v DD`
- `:n` replaces `n`
- `:p` replaces `p`
- `:s` replaces `s`
- `:q` replaces `q`

The legacy day editor behind `e DD` does not need to remain a first-class TUI action. It may remain only as an internal fallback or be removed from the new interaction model entirely.

The CLI subcommands outside the TUI remain unchanged.

This means:

- `mplan add ...` still works
- `mplan sync` still works
- only the in-app interaction model changes

## Visual Direction

The interface should feel closer to `nvim` without abandoning the current grid.

### Statusline Styling

Use ANSI color in the bottom line for the mode label:

- `NORMAL`: green
- `INSERT`: blue
- `COMMAND`: yellow or orange

The rest of the statusline can stay neutral, with selected date and bucket on the right.

Example shapes:

- `NORMAL  方向键移动 · Tab切分区 · i编辑 · :命令                2026-07-10 午`
- `INSERT  新任务内容 · Esc保存                                 2026-07-10 午`
- `COMMAND :sq                                              2026-07-10 午`

### Detail Overlay Styling

The detail overlay should feel like a focused centered card:

- wider and taller than a single month cell
- bordered or boxed distinctly from the background grid
- background grid visually weakened with dim text rather than deleted outright
- active bucket section visually stronger than the other two

This is the main place for reading a full day's content.

### Grid Styling

Keep the existing grid structure.

Enhance only the active context:

- selected day remains highlighted
- selected bucket inside that day remains emphasized with compact markers such as `>午:`

Do not add a gray overlay or replace the grid with a different scene.

## Architecture

### Runtime Shape

Keep `src/mplan/app.py` as the default runtime.

Extend the current state machine with:

- `mode`
- `insert_buffer`
- `command_buffer`
- `status_message`
- `detail_open`
- `detail_focus_bucket`
- optional selected task index inside the detail view if per-task actions are added incrementally

The current `NORMAL` / `INSERT` flow should evolve into a three-mode controller rather than being replaced by another runtime stack.

### Command Execution Layer

Add a small pure command parser/executor layer that maps command aliases to state transitions or side effects.

Recommended responsibilities:

- parse `command_buffer`
- normalize aliases
- return one of:
  - state update
  - side effect request such as sync/view/edit/quit
  - error status

This can live in `app.py` if kept small, or in a tiny helper module if it improves clarity.

### Rendering Layer

The bottom line renderer should become mode-aware:

- render colored mode label
- render insert buffer or command buffer
- render passive status text in `NORMAL`
- render right-aligned date + bucket metadata when width allows

When width is tight, preserve:

1. mode label
2. active command/edit buffer
3. selected date

Drop secondary hint text before dropping core context.

The main renderer should also support a centered overlay pass:

- render the grid first
- dim or visually weaken the background when `detail_open`
- render the centered detail panel on top

### Task Entry Semantics

Pressing `i` should no longer rewrite an entire bucket string.

Instead:

- in `NORMAL`, `i` creates a new draft task in the active bucket
- in the detail overlay, `i` also creates a new draft task in the active bucket
- saving a new task inserts one `PlannerItem`

This preserves item identity and avoids deleting existing items only to recreate them.

Preserving `PlannerItem.id` and `external_event_id` for existing tasks is important so synced Apple Calendar events can be updated rather than duplicated.

## Error Handling

### Unknown Command

Unknown commands should:

- not crash
- clear command input
- return to `NORMAL`
- show a one-line status message

### Sync Failures

If sync fails, stay in the app and show the error in the bottom line instead of exiting.

For `:sq`, only quit after successful sync. If sync fails, stay in `NORMAL` and show the failure.

### View and Legacy Edit

If `:v` opens the detail overlay, exiting it should reliably restore the month grid without leaving the terminal in a half-cleared state.

The old legacy day editor should not be necessary for the main TUI flow.

## Testing Strategy

Add or update tests for:

- `NORMAL` ignores direct action keys such as `s` and `q`
- `:` enters `COMMAND`
- command buffer editing and cancel behavior
- `:q`, `:s`, `:sq`, `:v`, `:n`, `:p` alias handling
- unknown command handling
- `:sq` quits only after successful sync
- statusline rendering in `NORMAL`, `INSERT`, and `COMMAND`
- colorized mode label generation
- `Enter` opens the detail overlay
- `Esc` closes the detail overlay
- detail overlay shows imported events and all three buckets for the selected day
- `i` adds a new task instead of serializing and rewriting the whole bucket
- editing existing tasks preserves item identity so sync updates old owned calendar events instead of duplicating them
- old `v DD` prompt expectations removed from TUI-facing docs and tests

## Acceptance Criteria

This design is successful when:

- `NORMAL` mode is used only for selection
- sync, quit, month switching, and detail view are triggered through `COMMAND`
- both short and long command aliases work
- `:sq` syncs and then exits
- `Enter` or `:v` opens a centered day-detail overlay
- `i` creates a new task in the active bucket rather than appending to a serialized bucket line
- existing tasks keep their identity strongly enough for sync to update Calendar events instead of duplicating them
- the month grid remains the main visual structure
- the detail overlay feels like a focused larger expansion of the selected day
- the bottom line looks clearly mode-based and more `nvim`-like
- the app no longer mixes the old prompt-command model with the new mode model
