from datetime import date

from mplan.tui import handle_keypress
from mplan.tui_state import TuiState


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
