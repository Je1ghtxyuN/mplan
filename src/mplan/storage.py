import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from mplan.models import PlannerItem


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists planner_items (
                    id text primary key,
                    day text not null,
                    bucket text not null,
                    text text not null,
                    completed integer not null,
                    created_at text not null,
                    updated_at text not null,
                    external_event_id text
                )
                """
            )

    def upsert_planner_item(self, item: PlannerItem) -> PlannerItem:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into planner_items (
                    id, day, bucket, text, completed, created_at, updated_at, external_event_id
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                    day=excluded.day,
                    bucket=excluded.bucket,
                    text=excluded.text,
                    completed=excluded.completed,
                    updated_at=excluded.updated_at,
                    external_event_id=excluded.external_event_id
                """,
                (
                    item.id,
                    item.day.isoformat(),
                    item.bucket,
                    item.text,
                    int(item.completed),
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    item.external_event_id,
                ),
            )
        return item

    def list_day_items(self, day: date) -> list[PlannerItem]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select id, day, bucket, text, completed, created_at, updated_at, external_event_id
                from planner_items
                where day = ?
                order by created_at, id
                """,
                (day.isoformat(),),
            ).fetchall()
        return [self._planner_item_from_row(row) for row in rows]

    def set_completed(self, item_id: str, completed: bool) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                update planner_items
                set completed = ?, updated_at = ?
                where id = ?
                """,
                (int(completed), datetime.now(UTC).isoformat(), item_id),
            )

    def attach_external_event_id(self, item_id: str, event_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                update planner_items
                set external_event_id = ?, updated_at = ?
                where id = ?
                """,
                (event_id, datetime.now(UTC).isoformat(), item_id),
            )

    def list_days_in_month(self, year: int, month: int) -> list[date]:
        month_prefix = f"{year:04d}-{month:02d}-"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select distinct day
                from planner_items
                where day like ?
                order by day
                """,
                (f"{month_prefix}%",),
            ).fetchall()
        return [date.fromisoformat(row[0]) for row in rows]

    def _planner_item_from_row(self, row: tuple[str, str, str, str, int, str, str, str | None]) -> PlannerItem:
        return PlannerItem(
            id=row[0],
            day=date.fromisoformat(row[1]),
            bucket=row[2],
            text=row[3],
            completed=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            external_event_id=row[7],
        )
