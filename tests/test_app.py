from __future__ import annotations

from datetime import date
import time
from types import SimpleNamespace

from mplan import app


def test_handle_normal_command_tab_cycles_bucket():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "早",
        "mode": "NORMAL",
        "buffer": "",
        "status": "",
    }

    updated = app._handle_normal_command(state, "\t")

    assert updated["bucket"] == "午"


def test_fit_grid_rows_for_statusline_keeps_last_line_for_status():
    rows = [f"row-{index}" for index in range(20)]

    fitted = app._fit_grid_rows_for_statusline(rows, total_lines=10)

    assert len(fitted) == 9
    assert fitted == rows[:9]


def test_handle_insert_key_escape_saves_and_returns_normal():
    saved = []
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "INSERT",
        "buffer": "resume | english",
        "status": "",
    }

    updated = app._handle_insert_key(
        state,
        "ESC",
        save_func=lambda day, bucket, raw: saved.append((day, bucket, raw)),
    )

    assert saved == [(date(2026, 7, 10), "午", "resume | english")]
    assert updated["mode"] == "NORMAL"
    assert updated["status"] == "已保存"


def test_handle_insert_key_enter_does_not_save_or_exit():
    saved = []
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "INSERT",
        "buffer": "resume | english",
        "status": "",
    }

    updated = app._handle_insert_key(
        state,
        "ENTER",
        save_func=lambda day, bucket, raw: saved.append((day, bucket, raw)),
    )

    assert saved == []
    assert updated["mode"] == "INSERT"
    assert updated["buffer"] == "resume | english"


def test_handle_normal_command_arrow_moves_selection_across_month():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 31),
        "bucket": "早",
        "mode": "NORMAL",
        "buffer": "",
        "status": "",
    }

    updated = app._handle_normal_command(state, "RIGHT")

    assert updated["selected"] == date(2026, 8, 1)
    assert updated["current"] == date(2026, 8, 1)


def test_handle_normal_command_colon_enters_command_mode():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "status": "",
    }

    updated = app._handle_normal_command(state, ":")

    assert updated["mode"] == "COMMAND"
    assert updated["command_buffer"] == ":"


def test_handle_normal_command_enter_opens_detail_overlay():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "status": "",
    }

    updated = app._handle_normal_command(state, "ENTER")

    assert updated["detail_open"] is True


def test_handle_normal_command_legacy_actions_require_command_mode():
    sync_calls = []
    edit_calls = []
    view_calls = []
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "command_buffer": "",
        "detail_open": False,
        "status": "",
    }

    for key in ("q", "s", "v", "e", "n", "p"):
        updated = app._handle_normal_command(state, key)

        assert updated.get("quit") is None
        assert updated["mode"] == "NORMAL"
        assert updated["current"] == date(2026, 7, 1)
        assert updated["selected"] == date(2026, 7, 10)
        assert updated["status"] == "NORMAL仅选择 用:执行命令"

    assert sync_calls == []
    assert edit_calls == []
    assert view_calls == []


def test_handle_command_key_executes_syncquit_command():
    calls = []
    state = {
        "mode": "COMMAND",
        "command_buffer": ":sq",
        "status": "",
    }

    updated = app._handle_command_key(
        state,
        "ENTER",
        command_func=lambda command: calls.append(command) or {"quit": True, "status": "已同步"},
    )

    assert calls == ["syncquit"]
    assert updated["quit"] is True


def test_execute_sync_command_reports_failure_without_crashing():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
    }

    sync_engine = SimpleNamespace(
        sync_month=lambda year, month: (_ for _ in ()).throw(RuntimeError("calendar unavailable"))
    )

    updated = app._execute_command(state, "sync", sync_engine, lambda day: None)

    assert updated == {"status": "同步失败: calendar unavailable"}


def test_execute_syncquit_stays_open_when_sync_fails():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
    }

    sync_engine = SimpleNamespace(
        sync_month=lambda year, month: (_ for _ in ()).throw(RuntimeError("calendar unavailable"))
    )

    updated = app._execute_command(state, "syncquit", sync_engine, lambda day: None)

    assert updated == {"status": "同步失败: calendar unavailable"}


def test_handle_command_key_view_opens_overlay_and_escape_closes_it():
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "COMMAND",
        "command_buffer": ":v",
        "detail_open": False,
        "status": "",
    }

    opened = app._handle_command_key(
        state,
        "ENTER",
        command_func=lambda command: app._execute_command(
            state,
            command,
            SimpleNamespace(sync_month=lambda *_: None),
            lambda day: None,
        ),
    )

    assert opened["mode"] == "NORMAL"
    assert opened["detail_open"] is True

    closed = app._handle_normal_command(opened, "ESC")

    assert closed["detail_open"] is False


def test_run_app_syncquit_flows_through_command_mode(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 10)

    class FakeStore:
        def list_days_in_month(self, year, month):
            return []

        def list_day_items(self, day):
            return []

        def list_bucket_items(self, day, bucket):
            return []

        def create_planner_item(self, item):
            return item

    sync_calls = []
    store = FakeStore()
    sync_engine = SimpleNamespace(
        pull_month=lambda year, month: [],
        sync_month=lambda year, month: sync_calls.append((year, month))
        or SimpleNamespace(imported_count=1, exported_count=0, updated_count=0, warning=None),
    )
    keys = iter([":", "s", "q", "ENTER"])

    monkeypatch.setattr(app, "date", FixedDate)
    monkeypatch.setattr(app, "_read_key", lambda mode="NORMAL": next(keys))
    monkeypatch.setattr(app, "_render_app", lambda store, sync_engine, state: None)

    assert app.run_app(store, sync_engine) == 0
    assert sync_calls == [(2026, 7)]


def test_decode_escape_sequence_supports_ss3_and_csi_arrows():
    assert app._decode_escape_sequence("OA") == "UP"
    assert app._decode_escape_sequence("OB") == "DOWN"
    assert app._decode_escape_sequence("[C") == "RIGHT"
    assert app._decode_escape_sequence("[1;5D") == "LEFT"


def test_consume_pending_key_reassembles_split_arrow_sequence():
    app._PENDING_KEY_BYTES = "\x1b"
    app._PENDING_KEY_DEADLINE = time.monotonic() + 1

    assert app._consume_pending_key("[") == ""
    assert app._consume_pending_key("C") == "RIGHT"


def test_read_key_returns_escape_when_no_followup_bytes_arrive(monkeypatch):
    class FakeStdin:
        def isatty(self):
            return True

        def fileno(self):
            return 0

        def read(self, size):
            return "\x1b"

    times = iter([0.0, 0.5])

    monkeypatch.setattr(app.sys, "stdin", FakeStdin())
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(app.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(app.select, "select", lambda reads, writes, errors, timeout: ([], [], []))

    assert app._read_key("NORMAL") == "ESC"


def test_read_key_reassembles_arrow_sequence_within_single_call(monkeypatch):
    class FakeStdin:
        def __init__(self, chars):
            self._chars = iter(chars)

        def isatty(self):
            return True

        def fileno(self):
            return 0

        def read(self, size):
            return next(self._chars)

    select_results = iter([([object()], [], []), ([object()], [], [])])
    timeline = [0.0, 0.01, 0.02, 0.03, 0.20]

    def fake_monotonic():
        if len(timeline) > 1:
            return timeline.pop(0)
        return timeline[0]

    monkeypatch.setattr(app.sys, "stdin", FakeStdin(["\x1b", "[", "C"]))
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(app.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, writes, errors, timeout: next(select_results),
    )

    assert app._read_key("NORMAL") == "RIGHT"


def test_read_key_supports_ss3_arrow_sequence_within_single_call(monkeypatch):
    class FakeStdin:
        def __init__(self, chars):
            self._chars = iter(chars)

        def isatty(self):
            return True

        def fileno(self):
            return 0

        def read(self, size):
            return next(self._chars)

    select_results = iter([([object()], [], []), ([object()], [], [])])
    timeline = [0.0, 0.01, 0.02, 0.03, 0.20]

    def fake_monotonic():
        if len(timeline) > 1:
            return timeline.pop(0)
        return timeline[0]

    monkeypatch.setattr(app.sys, "stdin", FakeStdin(["\x1b", "O", "C"]))
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(app.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(
        app.select,
        "select",
        lambda reads, writes, errors, timeout: next(select_results),
    )

    assert app._read_key("NORMAL") == "RIGHT"


def test_run_app_insert_save_and_command_syncquit(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 10)

    class FakeStore:
        def __init__(self):
            self.saved = []

        def list_days_in_month(self, year, month):
            return []

        def list_day_items(self, day):
            return []

        def create_planner_item(self, item):
            self.saved.append(("create", item.day, item.bucket, item.text))
            return item

    store = FakeStore()
    sync_calls = []
    sync_engine = SimpleNamespace(
        pull_month=lambda year, month: [],
        sync_month=lambda year, month: sync_calls.append((year, month))
        or SimpleNamespace(imported_count=1, exported_count=0, updated_count=0, warning=None),
    )
    keys = iter(["i", "A", "ESC", ":", "s", "q", "ENTER"])

    monkeypatch.setattr(app, "date", FixedDate)
    monkeypatch.setattr(app, "_read_key", lambda mode="NORMAL": next(keys))
    monkeypatch.setattr(app, "_render_app", lambda store, sync_engine, state: None)

    assert app.run_app(store, sync_engine) == 0
    assert ("create", date(2026, 7, 10), "早", "A") in store.saved
    assert sync_calls == [(2026, 7)]


def test_render_app_reserves_last_terminal_line_for_status(monkeypatch, capsys):
    state = {
        "current": date(2026, 7, 1),
        "selected": date(2026, 7, 10),
        "bucket": "午",
        "mode": "NORMAL",
        "buffer": "",
        "status": "已保存",
    }

    monkeypatch.setattr(app, "_collect_month_rows", lambda *args, **kwargs: [f"row-{i}" for i in range(20)])
    monkeypatch.setattr(app.shutil, "get_terminal_size", lambda fallback: SimpleNamespace(columns=80, lines=10))

    app._render_app(object(), object(), state)

    lines = capsys.readouterr().out.splitlines()
    assert "row-9" not in lines
    assert "NORMAL" in lines[-1]
    assert "2026-07-10 | 午 | 已保存" in lines[-1]
