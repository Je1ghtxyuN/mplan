from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from mplan.models import PlannerBucket

EditorMode = Literal["NORMAL", "INSERT"]
BUCKET_ORDER: tuple[PlannerBucket, ...] = ("早", "午", "晚")


@dataclass(frozen=True)
class TuiState:
    visible_year: int
    visible_month: int
    selected_day: date
    selected_bucket: PlannerBucket
    mode: EditorMode
    edit_buffer: str
    status_message: str

    @classmethod
    def initial(cls, selected_day: date) -> "TuiState":
        return cls(
            visible_year=selected_day.year,
            visible_month=selected_day.month,
            selected_day=selected_day,
            selected_bucket="早",
            mode="NORMAL",
            edit_buffer="",
            status_message="",
        )


def cycle_bucket(bucket: PlannerBucket, reverse: bool = False) -> PlannerBucket:
    index = BUCKET_ORDER.index(bucket)
    step = -1 if reverse else 1
    return BUCKET_ORDER[(index + step) % len(BUCKET_ORDER)]


def enter_insert_mode(state: TuiState, initial_text: str) -> TuiState:
    return TuiState(
        visible_year=state.visible_year,
        visible_month=state.visible_month,
        selected_day=state.selected_day,
        selected_bucket=state.selected_bucket,
        mode="INSERT",
        edit_buffer=initial_text,
        status_message=state.status_message,
    )


def exit_insert_mode(state: TuiState, status_message: str = "") -> TuiState:
    return TuiState(
        visible_year=state.visible_year,
        visible_month=state.visible_month,
        selected_day=state.selected_day,
        selected_bucket=state.selected_bucket,
        mode="NORMAL",
        edit_buffer="",
        status_message=status_message,
    )


def serialize_bucket_text(items: list[str]) -> str:
    return " | ".join(items)


def parse_bucket_text(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]
