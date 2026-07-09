# mplan

Month-grid terminal planner with Apple Calendar sync.

## Install

```bash
cd /Users/je1ghtxyun/code/mplan
python3 -m venv .venv
./.venv/bin/pip install -e .
```

## First Run

```bash
cd /Users/je1ghtxyun/code/mplan
./.venv/bin/mplan doctor
./.venv/bin/mplan
```

Grant Terminal calendar automation access when macOS prompts you.

## Commands

```bash
mplan                 # open the month view
mplan add 7/12 早 看论文
mplan add 7/12 午 改简历
mplan done 7/12 晚 1
mplan sync
mplan doctor
```

## TUI Controls

```bash
mplan
```

- Arrow keys move between days
- `Tab` switches `早 / 午 / 晚`
- `i` enters insert mode for the selected bucket
- `Esc` saves the selected bucket locally and returns to normal mode
- `s` syncs the visible month with Calendar
- `q` quits

## Notes

- The project is designed for macOS because it automates Calendar.app with AppleScript.
- The repository can be cloned and used on any Mac, but each machine needs its own virtual environment and Calendar permission grant.
