from datetime import date

import pytest

from mplan.models import PlannerItem
from mplan.storage import Store


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
