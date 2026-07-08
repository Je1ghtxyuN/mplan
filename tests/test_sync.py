from dataclasses import replace
from datetime import date, datetime

from mplan.models import PlannerItem
from mplan.sync import SyncEngine


class FakeStore:
    def __init__(self) -> None:
        self._items: dict[date, list[PlannerItem]] = {}
        self.attached: list[tuple[str, str]] = []

    def seed_items(self, items: list[PlannerItem]) -> None:
        for item in items:
            self._items.setdefault(item.day, []).append(item)

    def seed_owned_item(
        self, item: PlannerItem, external_event_id: str
    ) -> PlannerItem:
        owned = replace(item, external_event_id=external_event_id)
        self.seed_items([owned])
        return owned

    def list_day_items(self, day: date) -> list[PlannerItem]:
        return list(self._items.get(day, []))

    def attach_external_event_id(self, item_id: str, event_id: str) -> None:
        self.attached.append((item_id, event_id))

    def list_days_in_month(self, year: int, month: int) -> list[date]:
        return sorted(
            day for day in self._items if day.year == year and day.month == month
        )


class FakeBridge:
    def __init__(self) -> None:
        self.upserts: list[dict[str, object]] = []
        self.imports: list[object] = []

    def upsert_owned_event(self, item: PlannerItem, order_index: int) -> str:
        event_id = item.external_event_id or f"generated-{len(self.upserts) + 1}"
        self.upserts.append(
            {
                "item_id": item.id,
                "event_id": event_id,
                "title": f"{'✓ ' if item.completed else ''}{item.bucket}｜{item.text}",
                "order_index": order_index,
            }
        )
        return event_id

    def list_timed_events(self, month_start: date, month_end: date) -> list[object]:
        return list(self.imports)


def test_push_day_creates_one_event_per_planner_item():
    item_a = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    item_b = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="回消息")
    fake_store = FakeStore()
    fake_store.seed_items([item_a, item_b])
    fake_bridge = FakeBridge()

    engine = SyncEngine(fake_store, fake_bridge)
    engine.push_day(date(2026, 7, 12))

    assert [call["title"] for call in fake_bridge.upserts] == ["早｜看论文", "早｜回消息"]
    assert [call["order_index"] for call in fake_bridge.upserts] == [0, 1]


def test_push_day_updates_existing_owned_event():
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料")
    fake_store = FakeStore()
    owned = fake_store.seed_owned_item(item, external_event_id="owned-1")
    fake_bridge = FakeBridge()

    engine = SyncEngine(fake_store, fake_bridge)
    engine.push_day(date(2026, 7, 12))

    assert fake_bridge.upserts[0]["event_id"] == "owned-1"
    assert fake_store.attached == [(owned.id, "owned-1")]


def test_sync_month_reports_imported_and_exported_counts():
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="改简历")
    fake_store = FakeStore()
    fake_store.seed_items([item])
    fake_bridge = FakeBridge()
    fake_bridge.imports = [{"title": "腾讯会议"}]

    engine = SyncEngine(fake_store, fake_bridge)
    report = engine.sync_month(2026, 7)

    assert report.imported_count == 1
    assert report.exported_count == 1
    assert report.updated_count == 0
