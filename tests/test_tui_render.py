from dataclasses import replace
from datetime import date
from datetime import datetime

from mplan.models import ImportedCalendarEvent, PlannerItem
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
    state = replace(
        TuiState.initial(selected_day=date(2026, 7, 12)),
        status_message="已保存",
    )

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
    assert "已保存" in view["footer"]
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


def test_build_screen_view_leaves_room_for_footer_under_small_height(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    for day_number in range(1, 20):
        store.upsert_planner_item(
            PlannerItem.new(
                day=date(2026, 7, day_number),
                bucket="早",
                text=f"事项{day_number}",
            )
        )
    state = replace(
        TuiState.initial(selected_day=date(2026, 7, 12)),
        status_message="已保存",
    )

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=140,
        height=6,
    )

    assert len(view["body"]) <= 4
    rendered_lines = [view["header"], *view["body"], view["footer"]]
    assert len(rendered_lines) <= 6
    assert "已保存" in rendered_lines[-1]


def test_build_screen_view_keeps_footer_single_line_when_edit_buffer_has_newlines(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    state = enter_insert_mode(
        TuiState.initial(selected_day=date(2026, 7, 12)),
        "第一行\n第二行",
    )

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=140,
        height=40,
    )

    assert "\n" not in view["footer"]
    assert "第一行" in view["footer"]
    assert "第二行" in view["footer"]


def test_build_screen_view_keeps_visible_day_content_in_month_body(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 14), bucket="午", text="改简历")
    )
    store.replace_imported_events_in_month(
        2026,
        7,
        [
            ImportedCalendarEvent(
                id="evt-1",
                title="腾讯会议",
                starts_at=datetime.fromisoformat("2026-07-14T09:00:00"),
                ends_at=datetime.fromisoformat("2026-07-14T10:00:00"),
                calendar_name="工作",
                notes=None,
            )
        ],
    )
    state = TuiState.initial(selected_day=date(2026, 7, 12))

    view = build_screen_view(
        store,
        SyncEngine(store, DummyBridge()),
        state,
        width=140,
        height=40,
    )

    body = "\n".join(view["body"])
    assert "14" in body
    assert "正式: 09:00 腾讯会议" in body
    assert "午: 改简历" in body


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
