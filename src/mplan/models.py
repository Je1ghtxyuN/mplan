from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Literal
from uuid import uuid4

PlannerBucket = Literal["早", "午", "晚"]


@dataclass(frozen=True)
class PlannerItem:
    id: str
    day: date
    bucket: PlannerBucket
    text: str
    completed: bool
    created_at: datetime
    updated_at: datetime
    external_event_id: str | None = None

    @classmethod
    def new(cls, day: date, bucket: PlannerBucket, text: str) -> "PlannerItem":
        now = datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            day=day,
            bucket=bucket,
            text=text,
            completed=False,
            created_at=now,
            updated_at=now,
        )

    def with_completed(self, completed: bool) -> "PlannerItem":
        return replace(self, completed=completed, updated_at=datetime.now(UTC))
