import json
import subprocess
from dataclasses import dataclass, replace
from datetime import date, datetime

from mplan.models import ImportedCalendarEvent, PlannerItem
from mplan.sync import SyncEngine


class FakeStore:
    def __init__(self) -> None:
        self._items: dict[date, list[PlannerItem]] = {}
        self.attached: list[tuple[str, str]] = []
        self.imported_cache: dict[tuple[int, int], list[ImportedCalendarEvent]] = {}

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

    def replace_imported_events_in_month(
        self, year: int, month: int, events: list[ImportedCalendarEvent]
    ) -> None:
        self.imported_cache[(year, month)] = list(events)

    def list_imported_events_in_month(
        self, year: int, month: int
    ) -> list[ImportedCalendarEvent]:
        return list(self.imported_cache.get((year, month), []))


class FakeBridge:
    def __init__(self) -> None:
        self.upserts: list[dict[str, object]] = []
        self.imports: list[object] = []
        self.raise_on_fetch: Exception | None = None
        self.migrated_event_ids: dict[str, tuple[str, str | None]] = {}
        self.list_calls: list[tuple[date, date]] = []

    def upsert_owned_event(
        self, item: PlannerItem, order_index: int
    ) -> tuple[str, str | None]:
        event_id, deleted_event_id = self.migrated_event_ids.get(
            item.id,
            (item.external_event_id or f"generated-{len(self.upserts) + 1}", None),
        )
        self.upserts.append(
            {
                "item_id": item.id,
                "event_id": event_id,
                "deleted_event_id": deleted_event_id,
                "title": f"{'✓ ' if item.completed else ''}{item.bucket}｜{item.text}",
                "order_index": order_index,
            }
        )
        return event_id, deleted_event_id

    def list_timed_events(self, month_start: date, month_end: date) -> list[object]:
        self.list_calls.append((month_start, month_end))
        return list(self.imports)

    def fetch_timed_events(self, month_start: date, month_end: date) -> list[object]:
        if self.raise_on_fetch is not None:
            raise self.raise_on_fetch
        return list(self.imports)


@dataclass(frozen=True)
class FakeImportedEvent:
    title: str
    notes: str | None = None


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


def test_sync_month_updates_external_event_id_after_migration():
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="改简历")
    fake_store = FakeStore()
    owned = fake_store.seed_owned_item(item, external_event_id="local-evt-1")
    fake_bridge = FakeBridge()
    fake_bridge.migrated_event_ids[owned.id] = ("icloud-evt-1", "local-evt-1")

    engine = SyncEngine(fake_store, fake_bridge)
    engine.sync_month(2026, 7)

    assert fake_store.attached == [(owned.id, "icloud-evt-1")]


def test_refresh_month_imports_excludes_mplan_owned_imports():
    fake_store = FakeStore()
    fake_bridge = FakeBridge()
    fake_bridge.imports = [
        FakeImportedEvent(title="腾讯会议"),
        FakeImportedEvent(
            title="早｜看论文",
            notes=json.dumps(
                {"source": "mplan", "item_id": "planner-1"}, ensure_ascii=False
            ),
        ),
    ]

    engine = SyncEngine(fake_store, fake_bridge)
    events, warning = engine.refresh_month_imports(2026, 7)

    assert [event.title for event in events] == ["腾讯会议"]
    assert warning is None


def test_pull_month_uses_live_bridge_fetch_and_filters_owned_imports():
    fake_store = FakeStore()
    fake_store.replace_imported_events_in_month(
        2026,
        7,
        [
            ImportedCalendarEvent(
                id="cached-evt",
                title="缓存会议",
                starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
                ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
                calendar_name="工作",
                notes=None,
            )
        ],
    )
    fake_bridge = FakeBridge()
    fake_bridge.imports = [
        FakeImportedEvent(title="直播会议"),
        FakeImportedEvent(
            title="午｜改简历",
            notes=json.dumps({"source": "mplan", "item_id": "planner-1"}, ensure_ascii=False),
        ),
    ]

    engine = SyncEngine(fake_store, fake_bridge)
    events = engine.pull_month(2026, 7)

    assert [event.title for event in events] == ["直播会议"]
    assert fake_bridge.list_calls == [(date(2026, 7, 1), date(2026, 7, 31))]


def test_cached_month_uses_store_cache_without_live_bridge_fetch():
    fake_store = FakeStore()
    cached = ImportedCalendarEvent(
        id="cached-evt",
        title="缓存会议",
        starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
        ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
        calendar_name="工作",
        notes=None,
    )
    fake_store.replace_imported_events_in_month(2026, 7, [cached])
    fake_bridge = FakeBridge()
    fake_bridge.imports = [FakeImportedEvent(title="直播会议")]

    engine = SyncEngine(fake_store, fake_bridge)
    events = engine.cached_month(2026, 7)

    assert [event.title for event in events] == ["缓存会议"]
    assert fake_bridge.list_calls == []


def test_push_day_uses_completion_prefix_for_completed_item():
    completed_item = PlannerItem.new(
        day=date(2026, 7, 12), bucket="晚", text="整理材料"
    ).with_completed(True)
    fake_store = FakeStore()
    fake_store.seed_items([completed_item])
    fake_bridge = FakeBridge()

    engine = SyncEngine(fake_store, fake_bridge)
    result = engine.push_day(date(2026, 7, 12))

    assert result is None
    assert fake_bridge.upserts[0]["title"] == "✓ 晚｜整理材料"


def test_sync_month_caches_visible_imports():
    fake_store = FakeStore()
    fake_bridge = FakeBridge()
    fake_bridge.imports = [
        ImportedCalendarEvent(
            id="evt-1",
            title="腾讯会议",
            starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
            ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
            calendar_name="工作",
            notes=None,
        )
    ]

    engine = SyncEngine(fake_store, fake_bridge)
    report = engine.sync_month(2026, 7)

    assert report.imported_count == 1
    assert fake_store.list_imported_events_in_month(2026, 7)[0].title == "腾讯会议"


def test_refresh_month_imports_falls_back_to_cached_events_on_failure():
    fake_store = FakeStore()
    cached = ImportedCalendarEvent(
        id="evt-cached",
        title="缓存会议",
        starts_at=datetime.fromisoformat("2026-07-12T09:00:00"),
        ends_at=datetime.fromisoformat("2026-07-12T10:00:00"),
        calendar_name="工作",
        notes=None,
    )
    fake_store.replace_imported_events_in_month(2026, 7, [cached])
    fake_bridge = FakeBridge()
    fake_bridge.raise_on_fetch = subprocess.TimeoutExpired(cmd=["osascript"], timeout=30)

    engine = SyncEngine(fake_store, fake_bridge)
    imported, warning = engine.refresh_month_imports(2026, 7)

    assert [event.title for event in imported] == ["缓存会议"]
    assert warning is not None
