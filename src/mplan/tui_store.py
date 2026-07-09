from __future__ import annotations

from datetime import date

from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.tui_state import parse_bucket_text, serialize_bucket_text


def load_bucket_text(store: Store, day: date, bucket: str) -> str:
    items = [item.text for item in store.list_day_items(day) if item.bucket == bucket]
    return serialize_bucket_text(items)


def save_bucket_text(store: Store, day: date, bucket: str, raw: str) -> list[str]:
    parsed = parse_bucket_text(raw)
    store.delete_day_bucket(day, bucket)
    for text in parsed:
        store.upsert_planner_item(PlannerItem.new(day=day, bucket=bucket, text=text))
    return parsed
