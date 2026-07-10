import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
import subprocess


@dataclass(frozen=True)
class SyncReport:
    imported_count: int
    exported_count: int
    updated_count: int
    warning: str | None = None


class SyncEngine:
    def __init__(self, store, bridge):
        self.store = store
        self.bridge = bridge

    def pull_month(self, year: int, month: int) -> list:
        return self.store.list_imported_events_in_month(year, month)

    def refresh_month_imports(self, year: int, month: int) -> tuple[list, str | None]:
        month_start, month_end = self._month_bounds(year, month)
        try:
            events = self.bridge.fetch_timed_events(month_start, month_end)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as exc:
            return self.pull_month(year, month), f"日历导入刷新失败，已显示上次同步结果: {exc}"

        visible_events = [event for event in events if not self._is_owned_event(event)]
        self.store.replace_imported_events_in_month(year, month, visible_events)
        return visible_events, None

    def push_day(self, day: date) -> None:
        items = self.store.list_day_items(day)
        bucket_counts = {"早": 0, "午": 0, "晚": 0}
        for item in items:
            order_index = bucket_counts[item.bucket]
            event_id, _deleted_event_id = self.bridge.upsert_owned_event(
                item, order_index=order_index
            )
            self.store.attach_external_event_id(item.id, event_id)
            bucket_counts[item.bucket] += 1

    def sync_month(self, year: int, month: int) -> SyncReport:
        imported_events, warning = self.refresh_month_imports(year, month)
        exported_count = 0
        updated_count = 0
        for day in self.store.list_days_in_month(year, month):
            day_items = self.store.list_day_items(day)
            exported_count += len(day_items)
            updated_count += sum(
                1 for item in day_items if item.external_event_id is not None
            )
            self.push_day(day)
        return SyncReport(
            imported_count=len(imported_events),
            exported_count=exported_count,
            updated_count=updated_count,
            warning=warning,
        )

    def _month_bounds(self, year: int, month: int) -> tuple[date, date]:
        last_day = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _is_owned_event(self, event) -> bool:
        notes = getattr(event, "notes", None)
        if not notes:
            return False
        try:
            metadata = json.loads(notes)
        except json.JSONDecodeError:
            return False
        return metadata.get("source") == "mplan"
