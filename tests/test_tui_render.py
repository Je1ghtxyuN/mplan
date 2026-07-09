from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.sync import SyncEngine
from mplan.tui_render import build_screen_view
from mplan.tui_state import TuiState, enter_insert_mode


class DummyBridge:
    def list_events(self, year: int, month: int):
        return []

    def upsert_event(self, *args, **kwargs):
        raise AssertionError("not used")


def test_build_screen_view_returns_footer_hints_in_normal_mode(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=140,
        height=40,
    )

    assert "NORMAL" in view["header"]
    assert isinstance(view["body"], list)
    assert view["body"]
    assert "Tab" in view["footer"]
    assert "editor_text" not in view


def test_build_screen_view_puts_active_edit_buffer_in_footer_in_insert_mode(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    )
    state = enter_insert_mode(TuiState.initial(selected_day=date(2026, 7, 12)), "看论文")

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=140,
        height=40,
    )

    assert "INSERT" in view["header"]
    assert "看论文" in view["footer"]
    assert "Esc保存" in view["footer"]
    assert "editor_text" not in view


def test_build_screen_view_marks_compact_mode_when_terminal_is_small(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=60,
        height=20,
    )

    assert view["layout"] == "compact"
    assert isinstance(view["body"], list)
