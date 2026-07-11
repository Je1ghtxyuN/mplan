from datetime import date
from datetime import datetime

import pytest

from mplan.models import ImportedCalendarEvent, PlannerItem
from mplan.storage import Store


def test_store_connect_context_closes_sqlite_connection(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()

    with store._connect() as conn:
        assert conn.execute("select 1").fetchall() == [(1,)]

    with pytest.raises(Exception):
        conn.execute("select 1")


def test_store_round_trips_multiple_bucket_items(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    )
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="回消息")
    )

    items = store.list_day_items(date(2026, 7, 12))
    assert [item.text for item in items] == ["看论文", "回消息"]
    assert all(item.bucket == "早" for item in items)


def test_store_marks_item_complete_without_deleting(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    item = store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料")
    )

    store.set_completed(item.id, True)
    reloaded = store.list_day_items(date(2026, 7, 12))[0]
    assert reloaded.completed is True
    assert reloaded.text == "整理材料"


def test_store_round_trips_required_afternoon_bucket(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="改简历")
    )

    items = store.list_day_items(date(2026, 7, 12))
    assert [item.bucket for item in items] == ["午"]


def test_invalid_bucket_is_rejected():
    with pytest.raises(ValueError, match="Invalid planner bucket"):
        PlannerItem.new(day=date(2026, 7, 12), bucket="中", text="过时命名")


def test_store_round_trips_imported_events_cache(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    event = ImportedCalendarEvent(
        id="evt-1",
        title="腾讯会议",
        starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
        ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
        calendar_name="工作",
        notes=None,
    )

    store.replace_imported_events_in_month(2026, 7, [event])
    cached = store.list_imported_events_in_month(2026, 7)

    assert len(cached) == 1
    assert cached[0].title == "腾讯会议"


def test_replace_imported_events_only_replaces_target_month(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    july_event = ImportedCalendarEvent(
        id="evt-july",
        title="七月会议",
        starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
        ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
        calendar_name="工作",
        notes=None,
    )
    august_event = ImportedCalendarEvent(
        id="evt-aug",
        title="八月会议",
        starts_at=datetime.fromisoformat("2026-08-12T09:00:00"),
        ends_at=datetime.fromisoformat("2026-08-12T10:00:00"),
        calendar_name="工作",
        notes=None,
    )

    store.replace_imported_events_in_month(2026, 7, [july_event])
    store.replace_imported_events_in_month(2026, 8, [august_event])
    store.replace_imported_events_in_month(2026, 7, [])

    assert store.list_imported_events_in_month(2026, 7) == []
    assert [event.title for event in store.list_imported_events_in_month(2026, 8)] == ["八月会议"]


def test_store_queries_work_even_if_parent_dir_was_missing(tmp_path):
    store = Store(tmp_path / "nested" / "mplan.db")

    items = store.list_day_items(date(2026, 7, 12))

    assert items == []


def test_update_planner_item_preserves_external_event_id(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    original = PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧内容")
    original = store.create_planner_item(original)
    store.attach_external_event_id(original.id, "evt-123")

    reloaded = store.list_day_items(date(2026, 7, 10))[0]
    updated = reloaded.with_text("新内容")
    store.update_planner_item(updated)

    final = store.list_day_items(date(2026, 7, 10))[0]
    assert final.id == original.id
    assert final.text == "新内容"
    assert final.external_event_id == "evt-123"


def test_list_bucket_items_returns_only_requested_bucket(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="看论文"))
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历"))

    items = store.list_bucket_items(date(2026, 7, 10), "午")

    assert [item.text for item in items] == ["改简历"]
