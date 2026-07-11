from types import SimpleNamespace

from mplan.cli import build_parser, launch_app, main
from mplan.doctor import run_doctor


def test_build_parser_supports_expected_subcommands():
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices
    assert {"add", "done", "sync", "doctor"} <= set(choices)


def test_main_returns_zero_for_doctor(monkeypatch):
    monkeypatch.setattr("mplan.cli.run_doctor", lambda: 0)
    assert main(["doctor"]) == 0


def test_main_defaults_to_app_launch(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.launch_app", lambda: calls.append("launch") or 0)
    assert main([]) == 0
    assert calls == ["launch"]


def test_launch_app_still_uses_grid_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.build_store", lambda: "store")
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: ("sync", store))
    monkeypatch.setattr(
        "mplan.cli.run_app",
        lambda store, sync_engine: calls.append((store, sync_engine)) or 0,
    )

    assert launch_app() == 0
    assert calls == [("store", ("sync", "store"))]


def test_add_command_routes_to_add_handler(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.handle_add", lambda args: calls.append(args.text) or 0)
    assert main(["add", "7/12", "早", "看论文"]) == 0
    assert calls == ["看论文"]


def test_sync_command_routes_to_sync_handler(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.handle_sync", lambda args: calls.append("sync") or 0)
    assert main(["sync"]) == 0
    assert calls == ["sync"]


def test_handle_sync_reports_failure_without_traceback(monkeypatch, capsys):
    class FakeSyncEngine:
        def __init__(self, store):
            pass

        def sync_month(self, year, month):
            raise RuntimeError("calendar unavailable")

    monkeypatch.setattr("mplan.cli.build_store", lambda: object())
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: FakeSyncEngine(store))

    assert main(["sync"]) == 1
    assert "同步失败: calendar unavailable" in capsys.readouterr().out


def test_handle_sync_reports_success(monkeypatch, capsys):
    class FakeSyncEngine:
        def __init__(self, store):
            pass

        def sync_month(self, year, month):
            return SimpleNamespace(
                imported_count=1,
                exported_count=2,
                updated_count=3,
                warning=None,
            )

    monkeypatch.setattr("mplan.cli.build_store", lambda: object())
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: FakeSyncEngine(store))

    assert main(["sync"]) == 0
    assert "已同步: 导入 1，导出 2，更新 3" in capsys.readouterr().out


def test_run_doctor_reports_target_calendar(monkeypatch, capsys):
    monkeypatch.setattr("mplan.doctor.default_data_dir", lambda: "/tmp/.mplan")
    monkeypatch.setattr("mplan.doctor.default_db_path", lambda: "/tmp/.mplan/mplan.db")

    class FakeBridge:
        def healthcheck(self):
            return True, "Calendar automation available"

        def calendar_status(self):
            return True, "Calendar::mplan"

    monkeypatch.setattr("mplan.doctor.CalendarBridge", lambda: FakeBridge())

    assert run_doctor() == 0
    out = capsys.readouterr().out
    assert "Target calendar: Calendar::mplan" in out
