from mplan.cli import build_parser, main


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
