from mplan.cli import build_parser, launch_app, main


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


def test_launch_app_uses_tui_runtime(monkeypatch):
    calls = []
    monkeypatch.setattr("mplan.cli.build_store", lambda: "store")
    monkeypatch.setattr("mplan.cli.build_sync_engine", lambda store: ("sync", store))
    monkeypatch.setattr(
        "mplan.cli.run_tui",
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
