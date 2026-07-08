import json
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from mplan.models import PlannerItem


@dataclass(frozen=True)
class ImportedEvent:
    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    calendar_name: str
    notes: str | None


class CalendarBridge:
    BUCKET_STARTS = {"早": time(8, 0), "午": time(13, 0), "晚": time(19, 0)}
    EVENT_DURATION_MINUTES = 30

    def _run_script(self, script: str) -> str:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def owned_title_for(
        self, item: PlannerItem, completed: bool | None = None
    ) -> str:
        is_done = item.completed if completed is None else completed
        prefix = "✓ " if is_done else ""
        return f"{prefix}{item.bucket}｜{item.text}"

    def event_window_for(
        self, item: PlannerItem, order_index: int
    ) -> tuple[datetime, datetime]:
        start = datetime.combine(item.day, self.BUCKET_STARTS[item.bucket])
        start += timedelta(minutes=self.EVENT_DURATION_MINUTES * order_index)
        return start, start + timedelta(minutes=self.EVENT_DURATION_MINUTES)

    def list_timed_events(
        self, month_start: date, month_end: date
    ) -> list[ImportedEvent]:
        script = self._list_script(month_start, month_end)
        payload = self._run_script(script)
        records = json.loads(payload) if payload else []
        return [
            ImportedEvent(
                id=record["id"],
                title=record["title"],
                starts_at=datetime.fromisoformat(record["starts_at"]),
                ends_at=datetime.fromisoformat(record["ends_at"]),
                calendar_name=record["calendar_name"],
                notes=record.get("notes"),
            )
            for record in records
            if not record.get("all_day", False)
        ]

    def upsert_owned_event(self, item: PlannerItem, order_index: int) -> str:
        title = self.owned_title_for(item)
        starts_at, ends_at = self.event_window_for(item, order_index)
        metadata = json.dumps(
            {
                "source": "mplan",
                "item_id": item.id,
                "bucket": item.bucket,
                "day": item.day.isoformat(),
            },
            ensure_ascii=False,
        )
        script = f"""
set eventTitle to "{self._escape(title)}"
set eventNotes to "{self._escape(metadata)}"
set eventStart to date "{starts_at.strftime('%A, %B %d, %Y at %H:%M:%S')}"
set eventEnd to date "{ends_at.strftime('%A, %B %d, %Y at %H:%M:%S')}"
return eventTitle
"""
        self._run_script(script)
        return item.external_event_id or item.id

    def delete_owned_event(self, event_id: str) -> None:
        script = f'return "delete:{self._escape(event_id)}"'
        self._run_script(script)

    def healthcheck(self) -> tuple[bool, str]:
        try:
            result = self._run_script('tell application "Calendar" to return name')
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            return False, str(exc)
        return True, result or "Calendar automation available"

    def _list_script(self, month_start: date, month_end: date) -> str:
        return f"""
set monthStart to "{month_start.isoformat()}"
set monthEnd to "{month_end.isoformat()}"
return "[]"
"""

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
