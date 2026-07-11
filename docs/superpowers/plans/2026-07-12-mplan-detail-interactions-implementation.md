# mplan Detail Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix grid overflow messaging and arrow input, then add aligned, selectable detail tasks with completion and calendar-safe deletion.

**Architecture:** Keep application state transitions in `app.py`, task persistence in `storage.py`, calendar ownership operations behind `CalendarBridge`, and display-width rendering in the existing grid/detail render modules. Detail actions operate only on flattened local task lists; imported events remain read-only.

**Tech Stack:** Python 3.13, SQLite, AppleScript Calendar bridge, pytest, setuptools/uv.

## Global Constraints

- Preserve all existing user changes in the dirty worktree.
- Imported calendar events are read-only.
- Synced tasks delete their owned Calendar event before their local SQLite row.
- A Calendar deletion failure must preserve the local task and its external identifier.
- Global `mplan` command resolution must be verified before publishing.

---

### Task 1: Grid overflow and key decoding

**Files:**
- Modify: `src/mplan/month_grid.py`
- Modify: `src/mplan/app.py`
- Test: `tests/test_month_grid.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: terminal CSI/SS3 byte sequences and `render_day_cell(cell, width, height)`.
- Produces: one logical arrow command per complete sequence and an overflow row containing only `...`.

- [ ] Add tests asserting overflowing cells contain `...` and no `v DD` text.
- [ ] Add tests asserting CSI, SS3, and parameterized arrow sequences decode in one read and move one date step.
- [ ] Run focused tests and confirm the new overflow assertion fails against the old hint.
- [ ] Replace the legacy overflow hint and simplify escape-sequence reading so partial bytes do not escape one `_read_key` call.
- [ ] Run `pytest tests/test_month_grid.py tests/test_app.py -q` and expect all tests to pass.

### Task 2: Detail selection and display-width alignment

**Files:**
- Modify: `src/mplan/detail_view.py`
- Modify: `src/mplan/app.py`
- Modify: `src/mplan/grid_edit.py`
- Test: `tests/test_detail_view.py`
- Test: `tests/test_app.py`
- Test: `tests/test_grid_edit.py`

**Interfaces:**
- Consumes: `bucket_items: dict[str, list[PlannerItem]]` and `detail_task_index`.
- Produces: a stable flattened local-task order and rows whose terminal display width is exactly the requested width.

- [ ] Add failing tests for selected-task markers, selection clamping, completion prefixes, mixed-width right-border alignment, and overlay shortcut status text.
- [ ] Run the focused tests and verify failures describe missing behavior.
- [ ] Implement display-aware trim/pad helpers and selected-task rendering in `detail_view.py`.
- [ ] Implement overlay-specific Up/Down state transitions and status text in `app.py`/`grid_edit.py`.
- [ ] Run `pytest tests/test_detail_view.py tests/test_app.py tests/test_grid_edit.py -q` and expect all tests to pass.

### Task 3: Completion and calendar-safe deletion

**Files:**
- Modify: `src/mplan/app.py`
- Modify: `src/mplan/storage.py` only if an existing persistence interface is insufficient.
- Test: `tests/test_app.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: selected local `PlannerItem`, `Store.set_completed`, `Store.delete_planner_item`, and `CalendarBridge.delete_owned_event` through the sync engine.
- Produces: Space toggles completion; `d` deletes unsynced tasks locally or deletes the owned Calendar event before local deletion.

- [ ] Add failing tests for completion toggling and updated selection state.
- [ ] Add failing tests for unsynced deletion, synced deletion call ordering, failure preservation, and imported-event non-selection.
- [ ] Run focused tests and verify each fails for the intended missing action.
- [ ] Implement action helpers and route overlay Space/`d` keys through them.
- [ ] Ensure failure results are returned as visible status without deleting local data.
- [ ] Run `pytest tests/test_app.py tests/test_storage.py -q` and expect all tests to pass.

### Task 4: Documentation, package, and end-to-end verification

**Files:**
- Modify: `README.md`
- Verify: `pyproject.toml`
- Verify: all source and test files in the intended worktree diff.

**Interfaces:**
- Consumes: `[project.scripts] mplan = "mplan.cli:main"`.
- Produces: documented shortcuts and an invocable global `mplan` entry point.

- [ ] Update README shortcut and deletion-consistency documentation.
- [ ] Run `git diff --check` and inspect the complete diff for unrelated/destructive changes.
- [ ] Run the full `pytest -q` suite and expect zero failures.
- [ ] Build/install using the repository's declared tooling, then run the resolved global `mplan --help` and `mplan doctor` or an equivalent non-destructive command.
- [ ] Confirm `gh --version`, `gh auth status`, remote, and current branch.
- [ ] Stage the intended complete worktree, commit without interactive signing if necessary, push `main`, and verify local HEAD equals `origin/main`.
