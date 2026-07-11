from __future__ import annotations

from datetime import date
from typing import Literal

from mplan.models import PlannerBucket, PlannerItem

GridMode = Literal["NORMAL", "INSERT", "COMMAND"]
InsertTarget = str | None
BUCKET_ORDER: tuple[PlannerBucket, ...] = ("早", "午", "晚")
COMMAND_ALIASES: dict[str, str] = {
    "q": "quit",
    "quit": "quit",
    "s": "sync",
    "sync": "sync",
    "sq": "syncquit",
    "syncquit": "syncquit",
    "v": "view",
    "view": "view",
    "n": "next",
    "next": "next",
    "p": "prev",
    "prev": "prev",
}


def cycle_bucket(bucket: PlannerBucket) -> PlannerBucket:
    index = BUCKET_ORDER.index(bucket)
    return BUCKET_ORDER[(index + 1) % len(BUCKET_ORDER)]


def serialize_bucket_items(items: list[str]) -> str:
    return " | ".join(items)


def parse_bucket_buffer(raw: str) -> list[str]:
    return [part.strip() for part in raw.split("|") if part.strip()]


def load_bucket_items(store, day: date, bucket: PlannerBucket) -> list[PlannerItem]:
    return store.list_bucket_items(day, bucket)


def create_bucket_task(store, day: date, bucket: PlannerBucket, text: str) -> PlannerItem:
    return store.create_planner_item(PlannerItem.new(day=day, bucket=bucket, text=text.strip()))


def update_bucket_task(store, item: PlannerItem, text: str) -> PlannerItem:
    updated = item.with_text(text.strip())
    return store.update_planner_item(updated)


def parse_command(raw: str) -> str:
    normalized = raw.strip()
    if normalized.startswith(":"):
        normalized = normalized[1:]
    return COMMAND_ALIASES.get(normalized, normalized)


def colorize_mode_label(mode: str) -> str:
    colors = {"NORMAL": "32", "INSERT": "34", "COMMAND": "33"}
    return f"\x1b[{colors.get(mode, '0')}m{mode}\x1b[0m"


def build_statusline(
    mode: GridMode,
    day: date,
    bucket: PlannerBucket,
    status: str,
    buffer: str = "",
) -> str:
    if mode == "INSERT":
        return f"{mode} | {day.isoformat()} | {bucket} | {buffer} | Esc保存"
    if mode == "COMMAND":
        return f"{mode} | {day.isoformat()} | {bucket} | {buffer or ':'}"

    tail = status or "方向键移动 Tab切分区 Enter详情 i新建 :命令"
    return f"{mode} | {day.isoformat()} | {bucket} | {tail}"
