# Task 4 Report: Extend month-grid view models for selected bucket highlighting

## Scope

- Modified `src/mplan/month_grid.py`
- Modified `tests/test_month_grid.py`
- Preserved existing local edits in both files and kept the implementation limited to selected-bucket metadata on month-grid cells.

## TDD Record

### Step 1: Added failing tests first

Added the two required tests from the brief:

- `test_build_month_grid_marks_selected_bucket_on_selected_day`
- `test_build_month_grid_does_not_mark_bucket_on_unselected_days`

### Step 2: Verified RED

Initial command from the brief, `pytest tests/test_month_grid.py -v`, was not available on `PATH`, so I used the project virtualenv:

```bash
./.venv/bin/pytest tests/test_month_grid.py -v
```

Observed failure:

- `TypeError: build_month_grid() got an unexpected keyword argument 'selected_bucket'`

This matched the expected missing-interface failure from the brief.

### Step 3: Minimal implementation

Implemented only the required API extension:

- Added `DayCell.selected_bucket: str | None = None`
- Extended `build_month_grid(..., selected_bucket: str = "早")`
- Set `selected_bucket` on the selected day only
- Left all other month-grid behavior unchanged

Note: `DayCell.selected_bucket` was given a default of `None` so existing rendering tests and current local edits could remain intact without unrelated constructor churn.

### Step 4: Verified GREEN

Command:

```bash
./.venv/bin/pytest tests/test_month_grid.py -v
```

Result:

- `8 passed`

## Files Changed

### `tests/test_month_grid.py`

- Added the two selected-bucket tests from the brief.

### `src/mplan/month_grid.py`

- Added `selected_bucket` to `DayCell`
- Added `selected_bucket` parameter to `build_month_grid`
- Populated `selected_bucket` only when `day == selected_day`

## Commit

Created commit:

- `feat: track selected bucket in month grid`

## Concerns

- None functionally. The only small adaptation from the brief was using `./.venv/bin/pytest` because `pytest` was not directly available on `PATH`.
