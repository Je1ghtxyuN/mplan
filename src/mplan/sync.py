from calendar import monthrange
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SyncReport:
    imported_count: int
    exported_count: int
    updated_count: int


class SyncEngine:
    def __init__(self, store, bridge):
        self.store = store
        self.bridge = bridge

    def pull_month(self, year: int, month: int):
        month_start, month_end = self._month_bounds(year, month)
        return self.bridge.list_timed_events(month_start, month_end)

    def push_day(self, day: date) -> tuple[int, int]:
        items = self.store.list_day_items(day)
        bucket_counts = {"早": 0, "午": 0, "晚": 0}
        exported_count = 0
        updated_count = 0
        for item in items:
            order_index = bucket_counts[item.bucket]
            had_external_event = item.external_event_id is not None
            event_id = self.bridge.upsert_owned_event(item, order_index=order_index)
            self.store.attach_external_event_id(item.id, event_id)
            bucket_counts[item.bucket] += 1
            exported_count += 1
            if had_external_event:
                updated_count += 1
        return exported_count, updated_count

    def sync_month(self, year: int, month: int) -> SyncReport:
        imported_events = self.pull_month(year, month)
        exported_count = 0
        updated_count = 0
        for day in self.store.list_days_in_month(year, month):
            day_exported, day_updated = self.push_day(day)
            exported_count += day_exported
            updated_count += day_updated
        return SyncReport(
            imported_count=len(imported_events),
            exported_count=exported_count,
            updated_count=updated_count,
        )

    def _month_bounds(self, year: int, month: int) -> tuple[date, date]:
        last_day = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
