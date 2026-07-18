# mplan Sync Spinner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate TUI synchronization progress without changing sync engine or standalone CLI behavior.

**Architecture:** Run the blocking month sync in one worker thread while the main TUI thread renders spinner frames. Feed the worker result back through the existing success/failure formatting path.

**Tech Stack:** Python 3.13 standard-library threading, pytest.

## Global Constraints

- Only TUI `:sync` and `:syncquit` are animated.
- No overlapping input or synchronization while the spinner is active.
- Sync failures leave the application open.

### Task 1: Spinner runner

**Files:**
- Modify: `src/mplan/app.py`
- Test: `tests/test_app.py`

- [ ] Add failing tests for multiple progress frames, success, failure, and syncquit behavior.
- [ ] Implement a background worker plus main-thread render loop.
- [ ] Route TUI sync commands through the runner while retaining existing result formatting.
- [ ] Run focused app tests.

### Task 2: Documentation and verification

**Files:**
- Modify: `README.md`

- [ ] Document the TUI sync spinner.
- [ ] Run the full test suite and diff checks.
- [ ] Verify global `mplan`, commit, and push `main`.
