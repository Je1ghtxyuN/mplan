import curses
from datetime import date
from types import SimpleNamespace

from mplan.tui import _draw_screen, _view_to_lines, handle_keypress
from mplan.tui_state import TuiState, enter_insert_mode


class DummyStore:
    pass


class DummySyncEngine:
    def __init__(self):
        self.calls = []

    def sync_month(self, year: int, month: int):
        self.calls.append((year, month))
        return type(
            "Report",
            (),
            {
                "imported_count": 0,
                "exported_count": 0,
                "updated_count": 0,
                "warning": "",
            },
        )()


def test_handle_keypress_tab_cycles_bucket():
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    updated, should_quit = handle_keypress(state, 9, DummyStore(), DummySyncEngine())

    assert updated.selected_bucket == "午"
    assert should_quit is False


def test_handle_keypress_q_requests_exit():
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    updated, should_quit = handle_keypress(
        state,
        ord("q"),
        DummyStore(),
        DummySyncEngine(),
    )

    assert updated == state
    assert should_quit is True


def test_handle_keypress_s_runs_month_sync():
    sync_engine = DummySyncEngine()
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    updated, should_quit = handle_keypress(state, ord("s"), DummyStore(), sync_engine)

    assert sync_engine.calls == [(2026, 7)]
    assert "已同步" in updated.status_message
    assert should_quit is False


def test_handle_keypress_enter_keeps_insert_buffer_single_line():
    state = enter_insert_mode(
        TuiState.initial(selected_day=date(2026, 7, 12)),
        "看论文",
    )

    updated, should_quit = handle_keypress(
        state,
        curses.KEY_ENTER,
        DummyStore(),
        DummySyncEngine(),
    )

    assert updated.edit_buffer == "看论文"
    assert "\n" not in updated.edit_buffer
    assert should_quit is False


def test_view_to_lines_falls_back_to_rendering_grid_when_body_missing():
    grid = SimpleNamespace(
        weeks=[
            [
                SimpleNamespace(day=date(2026, 7, 6), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 7), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 8), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 9), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 10), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 11), in_month=True, selected=False),
                SimpleNamespace(day=date(2026, 7, 12), in_month=True, selected=True),
            ]
        ]
    )

    lines = _view_to_lines(
        {
            "header": "2026-07 NORMAL",
            "grid": grid,
            "footer": "2026-07-12 早 方向键移动",
        }
    )

    assert lines == [
        "2026-07 NORMAL",
        " 06   07   08   09   10   11  [12]",
        "2026-07-12 早 方向键移动",
    ]


def test_view_to_lines_uses_footer_as_edit_surface():
    lines = _view_to_lines(
        {
            "header": "2026-07 INSERT",
            "body": ["[12] 13 14"],
            "footer": "2026-07-12 早 编辑: 看论文 Esc保存",
            "editor_text": "this should not be rendered separately",
        }
    )

    assert lines == [
        "2026-07 INSERT",
        "[12] 13 14",
        "2026-07-12 早 编辑: 看论文 Esc保存",
    ]


def test_draw_screen_writes_grid_body_and_footer(monkeypatch):
    class FakeScreen:
        def __init__(self):
            self.writes = []
            self.cleared = False
            self.refreshed = False

        def getmaxyx(self):
            return (6, 40)

        def clear(self):
            self.cleared = True

        def addnstr(self, row, col, text, limit):
            self.writes.append((row, col, text, limit))

        def refresh(self):
            self.refreshed = True

    def fake_build_screen_view(store, sync_engine, state, width: int, height: int):
        assert width == 40
        assert height == 6
        return {
            "header": "2026-07 NORMAL",
            "body": [" 06   07   08   09   10   11  [12]", "2026-07-12 早"],
            "footer": "2026-07-12 早 方向键移动",
        }

    monkeypatch.setattr("mplan.tui._load_build_screen_view", lambda: fake_build_screen_view)
    screen = FakeScreen()

    _draw_screen(
        screen,
        DummyStore(),
        DummySyncEngine(),
        TuiState.initial(selected_day=date(2026, 7, 12)),
    )

    assert screen.cleared is True
    assert screen.refreshed is True
    assert [text for _, _, text, _ in screen.writes] == [
        "2026-07 NORMAL",
        " 06   07   08   09   10   11  [12]",
        "2026-07-12 早",
        "2026-07-12 早 方向键移动",
    ]
