from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Literal

from mplan.models import PlannerBucket

EditorMode = Literal["NORMAL", "INSERT"]
Direction = Literal["left", "right", "up", "down"]
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


def move_selection(state: TuiState, direction: Direction) -> TuiState:
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(state.visible_year, state.visible_month)
    row_index = 0
    col_index = 0
    for week_i, week in enumerate(weeks):
        for col_i, day in enumerate(week):
            if day == state.selected_day:
                row_index = week_i
                col_index = col_i
                break
        else:
            continue
        break

    deltas = {
        "left": (0, -1),
        "right": (0, 1),
        "up": (-1, 0),
        "down": (1, 0),
    }
    row_delta, col_delta = deltas[direction]
    next_day = weeks[row_index][col_index]
    target_row = row_index + row_delta
    target_col = col_index + col_delta
    if 0 <= target_row < len(weeks) and 0 <= target_col < len(weeks[target_row]):
        next_day = weeks[target_row][target_col]
    else:
        offset_days = {"left": -1, "right": 1, "up": -7, "down": 7}[direction]
        next_day = state.selected_day.fromordinal(
            state.selected_day.toordinal() + offset_days
        )

    return TuiState(
        visible_year=next_day.year,
        visible_month=next_day.month,
        selected_day=next_day,
        selected_bucket=state.selected_bucket,
        mode=state.mode,
        edit_buffer=state.edit_buffer,
        status_message=state.status_message,
    )
