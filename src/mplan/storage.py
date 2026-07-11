from contextlib import contextmanager
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from mplan.models import ImportedCalendarEvent, PlannerItem


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path.expanduser()

    def initialize(self) -> None:
        with self._connect() as conn:
            self._ensure_schema(conn)

    def upsert_planner_item(self, item: PlannerItem) -> PlannerItem:
        with self._connect() as conn:
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

    def create_planner_item(self, item: PlannerItem) -> PlannerItem:
        return self.upsert_planner_item(item)

    def update_planner_item(self, item: PlannerItem) -> PlannerItem:
        return self.upsert_planner_item(item)

    def delete_planner_item(self, item_id: str) -> None:
        with self._connect() as conn:
            conn.execute("delete from planner_items where id = ?", (item_id,))

    def list_day_items(self, day: date) -> list[PlannerItem]:
        with self._connect() as conn:
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

    def list_bucket_items(self, day: date, bucket: str) -> list[PlannerItem]:
        return [item for item in self.list_day_items(day) if item.bucket == bucket]

    def set_completed(self, item_id: str, completed: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update planner_items
                set completed = ?, updated_at = ?
                where id = ?
                """,
                (int(completed), datetime.now(UTC).isoformat(), item_id),
            )

    def attach_external_event_id(self, item_id: str, event_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update planner_items
                set external_event_id = ?, updated_at = ?
                where id = ?
                """,
                (event_id, datetime.now(UTC).isoformat(), item_id),
            )

    def delete_day_bucket(self, day: date, bucket: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                delete from planner_items
                where day = ? and bucket = ?
                """,
                (day.isoformat(), bucket),
            )

    def list_days_in_month(self, year: int, month: int) -> list[date]:
        month_prefix = f"{year:04d}-{month:02d}-"
        with self._connect() as conn:
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

    def replace_imported_events_in_month(
        self, year: int, month: int, events: list[ImportedCalendarEvent]
    ) -> None:
        month_prefix = f"{year:04d}-{month:02d}-"
        with self._connect() as conn:
            conn.execute(
                """
                delete from imported_events
                where day like ?
                """,
                (f"{month_prefix}%",),
            )
            conn.executemany(
                """
                insert into imported_events (
                    id, day, title, starts_at, ends_at, calendar_name, notes
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.id,
                        event.starts_at.date().isoformat(),
                        event.title,
                        event.starts_at.isoformat(),
                        event.ends_at.isoformat(),
                        event.calendar_name,
                        event.notes,
                    )
                    for event in events
                ],
            )

    def list_imported_events_in_month(
        self, year: int, month: int
    ) -> list[ImportedCalendarEvent]:
        month_prefix = f"{year:04d}-{month:02d}-"
        with self._connect() as conn:
            rows = conn.execute(
                """
                select id, title, starts_at, ends_at, calendar_name, notes
                from imported_events
                where day like ?
                order by starts_at, id
                """,
                (f"{month_prefix}%",),
            ).fetchall()
        return [
            ImportedCalendarEvent(
                id=row[0],
                title=row[1],
                starts_at=datetime.fromisoformat(row[2]),
                ends_at=datetime.fromisoformat(row[3]),
                calendar_name=row[4],
                notes=row[5],
            )
            for row in rows
        ]

    @contextmanager
    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(self.db_path))
        except sqlite3.OperationalError as exc:
            raise sqlite3.OperationalError(
                f"{exc}; db_path={self.db_path}"
            ) from exc
        try:
            self._ensure_schema(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
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
        conn.execute(
            """
            create table if not exists imported_events (
                id text primary key,
                day text not null,
                title text not null,
                starts_at text not null,
                ends_at text not null,
                calendar_name text not null,
                notes text
            )
            """
        )

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
