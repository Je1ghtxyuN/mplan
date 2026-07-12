# mplan

`mplan` is a macOS terminal month planner that can synchronize tasks with
Apple Calendar. It provides a lightweight Vim-style interface with morning,
afternoon, and evening task buckets.

## Requirements

- macOS with Calendar.app
- Python 3.13 or newer
- A terminal with UTF-8 and ANSI color support
- A writable Calendar.app calendar named `mplan` under your iCloud account

Calendar synchronization is optional for local planning. It requires permission
for the terminal or Python process to access Calendar.app.

## Installation

Clone the repository and install it into a virtual environment:

```bash
git clone https://github.com/Je1ghtxyuN/mplan.git
cd mplan
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
```

Run the environment check before first use:

```bash
./.venv/bin/mplan doctor
```

If macOS asks for Calendar or Automation access, grant it to the terminal or
Python application that runs `mplan`. Permissions can be reviewed under
**System Settings → Privacy & Security**.

## Usage

```bash
./.venv/bin/mplan
```

The command-line helpers can also add, complete, and synchronize tasks:

```bash
mplan add 7/12 早 看论文
mplan add 7/12 午 改简历
mplan done 7/12 晚 1
mplan sync
mplan doctor
```

When the virtual environment is not activated, replace `mplan` with
`./.venv/bin/mplan`.

## Month View Controls

The month view uses `NORMAL`, `INSERT`, and `COMMAND` modes:

- Arrow keys move between dates.
- `Tab` switches the selected bucket across `早`, `午`, and `晚`.
- `Enter` opens the selected day's detail overlay.
- `i` enters insert mode and creates a task in the active bucket.
- `Esc` saves and leaves insert mode, or closes the detail overlay.
- `:` enters command mode.

Inside the detail overlay:

- `Tab` switches the active bucket across `早`, `午`, and `晚`.
- `↑` / `↓` selects a local mplan task.
- `i` edits the selected task, or adds one when the active bucket is empty;
  `Esc` saves the text.
- `Space` toggles the selected task between complete and incomplete.
- `d` deletes the selected local task.
- `Esc` closes the overlay.

Imported events from other calendars are read-only. When a local task has
already been exported, deleting it removes the matching event from the `mplan`
calendar first. If Calendar deletion fails, the local task is retained so the
operation can be retried safely.

Command mode accepts short and long forms:

- `:q` / `:quit` exits.
- `:s` / `:sync` synchronizes the visible month.
- `:sq` / `:syncquit` synchronizes and exits.
- `:v` / `:view` opens the selected day's detail overlay.
- `:n` / `:next` moves to the next month.
- `:p` / `:prev` moves to the previous month.

In `NORMAL` mode, `q`, `s`, `v`, `n`, and `p` do not execute directly; enter
command mode with `:` first.

## Calendar Synchronization

- `mplan` writes only its owned planner events to the writable calendar named
  `mplan`.
- Create that calendar manually under your iCloud account before synchronizing.
- Existing `mplan` events previously written to another writable calendar are
  migrated when they are synchronized again.
- If Calendar.app or the target calendar is unavailable, the application reports
  the failure and retains the last cached imported events.

Local data is stored in `~/.mplan/mplan.db`. It is not committed to the
repository or uploaded by `mplan`.

## Development

Install pytest in the virtual environment and run the test suite:

```bash
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest
```

## Uninstallation

Remove the cloned repository and, if you no longer need your local planner data,
delete `~/.mplan`. Removing the data directory permanently deletes locally stored
tasks and cached calendar events.

## License

This project is licensed under the [MIT License](LICENSE).
