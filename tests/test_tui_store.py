from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.tui_store import load_bucket_text, save_bucket_text


def test_load_bucket_text_joins_items_in_bucket(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    )
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="回消息")
    )

    assert load_bucket_text(store, date(2026, 7, 12), "早") == "看论文 | 回消息"


def test_save_bucket_text_replaces_existing_bucket_items(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="旧内容")
    )

    saved = save_bucket_text(store, date(2026, 7, 12), "午", "改简历 | 练口语")
    items = [
        item.text for item in store.list_day_items(date(2026, 7, 12)) if item.bucket == "午"
    ]

    assert saved == ["改简历", "练口语"]
    assert items == ["改简历", "练口语"]


def test_save_bucket_text_clears_bucket_when_input_is_empty(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.upsert_planner_item(
        PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料")
    )

    save_bucket_text(store, date(2026, 7, 12), "晚", " | ")
    items = [item for item in store.list_day_items(date(2026, 7, 12)) if item.bucket == "晚"]

    assert items == []
