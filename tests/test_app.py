from __future__ import annotations

from dataclasses import replace
from datetime import date
import threading
import time
from types import SimpleNamespace

from mplan import app
from mplan.models import PlannerItem


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
        save_func=lambda day, bucket, raw, existing=None: saved.append((day, bucket, raw)),
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
        save_func=lambda day, bucket, raw, existing=None: saved.append((day, bucket, raw)),
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


def test_run_sync_with_spinner_renders_frames_and_returns_success():
    release = threading.Event()
    rendered = []

    class BlockingSyncEngine:
        def sync_month(self, year, month):
            assert release.wait(1)
            return SimpleNamespace(
                imported_count=1,
                exported_count=2,
                updated_count=3,
                warning=None,
            )

    def render(progress_state):
        rendered.append(progress_state)
        if len(rendered) >= 2:
            release.set()

    result = app._run_sync_with_spinner(
        {
            "current": date(2026, 7, 1),
            "mode": "COMMAND",
            "command_buffer": ":s",
            "status": "",
        },
        BlockingSyncEngine(),
        render,
        frame_interval=0.001,
    )

    assert len(rendered) >= 2
    assert rendered[0]["status"] != rendered[1]["status"]
    assert all("正在同步" in frame["status"] for frame in rendered)
    assert all(frame["mode"] == "NORMAL" for frame in rendered)
    assert result == {"status": "已同步 导入1 导出2 更新3"}


def test_run_sync_with_spinner_reports_failure_and_syncquit_does_not_exit():
    rendered = []
    sync_engine = SimpleNamespace(
        sync_month=lambda *_: (_ for _ in ()).throw(RuntimeError("calendar unavailable"))
    )

    result = app._run_sync_with_spinner(
        {"current": date(2026, 7, 1), "mode": "COMMAND", "status": ""},
        sync_engine,
        lambda state: rendered.append(state),
        quit_after_success=True,
        frame_interval=0.001,
    )

    assert rendered
    assert "正在同步" in rendered[0]["status"]
    assert result == {"status": "同步失败: calendar unavailable"}


def test_run_sync_with_spinner_syncquit_exits_after_success():
    sync_engine = SimpleNamespace(
        sync_month=lambda *_: SimpleNamespace(
            imported_count=0, exported_count=1, updated_count=0, warning=None
        )
    )

    result = app._run_sync_with_spinner(
        {"current": date(2026, 7, 1), "mode": "COMMAND", "status": ""},
        sync_engine,
        lambda state: None,
        quit_after_success=True,
        frame_interval=0.001,
    )

    assert result == {"status": "已同步 导入0 导出1 更新0", "quit": True}


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
    monkeypatch.setattr(app.os, "read", lambda fd, size: b"\x1b")
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
    raw_bytes = iter([b"\x1b", b"[", b"C"])
    monkeypatch.setattr(app.os, "read", lambda fd, size: next(raw_bytes))
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
    raw_bytes = iter([b"\x1b", b"O", b"C"])
    monkeypatch.setattr(app.os, "read", lambda fd, size: next(raw_bytes))
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


def test_detail_arrow_keys_move_and_clamp_local_task_selection():
    state = {"detail_open": True, "detail_task_index": 0, "status": ""}
    items = [object(), object()]

    state = app._handle_detail_command(state, "DOWN", items, lambda *_: None, lambda *_: None)
    assert state["detail_task_index"] == 1
    state = app._handle_detail_command(state, "DOWN", items, lambda *_: None, lambda *_: None)
    assert state["detail_task_index"] == 1
    state = app._handle_detail_command(state, "UP", items, lambda *_: None, lambda *_: None)
    assert state["detail_task_index"] == 0


def test_detail_space_toggles_selected_task_completion():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")
    toggled = []
    state = {"detail_open": True, "detail_task_index": 0, "status": ""}

    updated = app._handle_detail_command(
        state,
        " ",
        [item],
        lambda selected: toggled.append((selected.id, not selected.completed)),
        lambda *_: None,
    )

    assert toggled == [(item.id, True)]
    assert updated["status"] == "已完成"


def test_detail_e_enters_edit_mode_for_selected_task():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧文字")
    state = {"detail_open": True, "detail_task_index": 0, "status": "", "mode": "NORMAL"}

    updated = app._handle_detail_command(
        state, "e", [item], lambda *_: None, lambda *_: None
    )

    assert updated["mode"] == "INSERT"
    assert updated["buffer"] == "旧文字"
    assert updated["edit_item"] == item
    assert updated["detail_open"] is True


def test_detail_i_starts_new_task_even_when_current_bucket_has_tasks():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="已有任务")
    state = {
        "detail_open": True,
        "detail_task_index": 0,
        "status": "",
        "mode": "NORMAL",
        "bucket": "午",
    }

    updated = app._handle_detail_command(
        state, "i", [item], lambda *_: None, lambda *_: None
    )

    assert updated["mode"] == "INSERT"
    assert updated["buffer"] == ""
    assert updated["edit_item"] is None
    assert updated["bucket"] == "午"
    assert updated["status"] == "新建任务"


def test_detail_e_reports_when_current_bucket_has_no_task_to_edit():
    morning = PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="早任务")
    state = {
        "detail_open": True,
        "detail_task_index": None,
        "status": "",
        "mode": "NORMAL",
        "bucket": "午",
    }

    updated = app._handle_detail_command(
        state, "e", [morning], lambda *_: None, lambda *_: None
    )

    assert updated["mode"] == "NORMAL"
    assert updated["status"] == "当前分区没有可编辑任务"


def test_detail_i_starts_new_task_when_day_has_no_local_tasks():
    state = {
        "detail_open": True,
        "detail_task_index": 0,
        "status": "",
        "mode": "NORMAL",
        "bucket": "午",
    }

    updated = app._handle_detail_command(
        state, "i", [], lambda *_: None, lambda *_: None
    )

    assert updated["mode"] == "INSERT"
    assert updated["buffer"] == ""
    assert updated["edit_item"] is None
    assert updated["bucket"] == "午"
    assert updated["detail_open"] is True
    assert updated["status"] == "新建任务"


def test_detail_tab_cycles_bucket_and_selects_first_task_in_new_bucket():
    morning = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="早任务")
    afternoon = PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="午任务")
    state = {
        "detail_open": True,
        "detail_task_index": 0,
        "status": "",
        "mode": "NORMAL",
        "bucket": "早",
    }

    updated = app._handle_detail_command(
        state, "\t", [morning, afternoon], lambda *_: None, lambda *_: None
    )

    assert updated["bucket"] == "午"
    assert updated["detail_task_index"] == 1


def test_detail_i_adds_to_current_bucket_when_only_other_buckets_have_tasks():
    morning = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="早任务")
    state = {
        "detail_open": True,
        "detail_task_index": 0,
        "status": "",
        "mode": "NORMAL",
        "bucket": "午",
    }

    updated = app._handle_detail_command(
        state, "i", [morning], lambda *_: None, lambda *_: None
    )

    assert updated["mode"] == "INSERT"
    assert updated["bucket"] == "午"
    assert updated["edit_item"] is None
    assert updated["buffer"] == ""


def test_insert_escape_updates_existing_detail_task_and_returns_to_detail():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧文字")
    saved = []
    state = {
        "selected": item.day,
        "bucket": item.bucket,
        "mode": "INSERT",
        "buffer": "新文字",
        "edit_item": item,
        "detail_open": True,
        "status": "",
    }

    updated = app._handle_insert_key(
        state,
        "ESC",
        save_func=lambda day, bucket, raw, existing: saved.append(
            (day, bucket, raw, existing)
        ),
    )

    assert saved == [(item.day, item.bucket, "新文字", item)]
    assert updated["mode"] == "NORMAL"
    assert updated["detail_open"] is True
    assert updated["edit_item"] is None
    assert updated["status"] == "已更新"


def test_read_key_uses_unbuffered_fd_bytes_for_arrow_sequence(monkeypatch):
    class BufferedStdin:
        def isatty(self):
            return True

        def fileno(self):
            return 7

        def read(self, size):
            raise AssertionError("text-buffered read must not be used")

    raw_bytes = iter([b"\x1b", b"[", b"B"])
    monkeypatch.setattr(app.sys, "stdin", BufferedStdin())
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(app.select, "select", lambda reads, writes, errors, timeout: ([7], [], []))
    monkeypatch.setattr(app.os, "read", lambda fd, size: next(raw_bytes))

    assert app._read_key("NORMAL") == "DOWN"


def test_read_key_decodes_multibyte_utf8_character_from_raw_fd(monkeypatch):
    class TtyStdin:
        def isatty(self):
            return True

        def fileno(self):
            return 7

    raw_bytes = iter([bytes([value]) for value in "中".encode("utf-8")])
    monkeypatch.setattr(app.sys, "stdin", TtyStdin())
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(app.os, "read", lambda fd, size: next(raw_bytes))

    assert app._read_key("INSERT") == "中"


def test_read_key_queues_all_characters_from_one_ime_commit(monkeypatch):
    class TtyStdin:
        def isatty(self):
            return True

        def fileno(self):
            return 7

    reads = []
    monkeypatch.setattr(app.sys, "stdin", TtyStdin())
    monkeypatch.setattr(app.termios, "tcgetattr", lambda fd: "settings")
    monkeypatch.setattr(app.termios, "tcsetattr", lambda fd, when, settings: None)
    monkeypatch.setattr(app.tty, "setraw", lambda fd: None)
    monkeypatch.setattr(
        app.os,
        "read",
        lambda fd, size: reads.append((fd, size)) or "你好呀".encode("utf-8"),
    )

    assert app._read_key("INSERT") == "你"
    assert app._read_key("INSERT") == "好"
    assert app._read_key("INSERT") == "呀"
    assert len(reads) == 1


def test_detail_deletes_unsynced_task_locally():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")
    deleted = []
    state = {"detail_open": True, "detail_task_index": 0, "status": ""}

    updated = app._handle_detail_command(
        state, "d", [item], lambda *_: None, lambda selected: deleted.append(selected.id)
    )

    assert deleted == [item.id]
    assert updated["status"] == "已删除"


def test_delete_synced_task_removes_calendar_event_before_local_row():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")
    item = replace(item, external_event_id="event-1")
    calls = []
    store = SimpleNamespace(delete_planner_item=lambda item_id: calls.append(("local", item_id)))
    sync_engine = SimpleNamespace(
        bridge=SimpleNamespace(delete_owned_event=lambda event_id: calls.append(("calendar", event_id)))
    )

    app._delete_task(store, sync_engine, item)

    assert calls == [("calendar", "event-1"), ("local", item.id)]


def test_delete_synced_task_preserves_local_row_when_calendar_delete_fails():
    item = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")
    item = replace(item, external_event_id="event-1")
    local_deletes = []
    store = SimpleNamespace(delete_planner_item=lambda item_id: local_deletes.append(item_id))
    sync_engine = SimpleNamespace(
        bridge=SimpleNamespace(
            delete_owned_event=lambda event_id: (_ for _ in ()).throw(RuntimeError("Calendar busy"))
        )
    )

    try:
        app._delete_task(store, sync_engine, item)
    except RuntimeError as exc:
        assert str(exc) == "Calendar busy"
    else:
        raise AssertionError("expected calendar deletion failure")

    assert local_deletes == []
