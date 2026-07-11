from datetime import date
import readline

from mplan.models import PlannerItem


BUCKETS = ("早", "午", "晚")


def edit_day(store, day: date) -> None:
    print(f"\n编辑 {day.isoformat()} 的计划")
    existing = store.list_day_items(day)
    for bucket in BUCKETS:
        bucket_items = [item for item in existing if item.bucket == bucket]
        current = " | ".join(item.text for item in bucket_items)
        print(f"{bucket} 当前: {current or '(空)'}")
        raw = _input_with_prefill(
            f"{bucket} 新内容（用 | 分隔，多留空表示保持不变，输入 - 清空）: ",
            current,
        ).strip()
        if raw == "":
            continue
        store.delete_day_bucket(day, bucket)
        if raw == "-":
            continue
        for chunk in [part.strip() for part in raw.split("|") if part.strip()]:
            store.upsert_planner_item(PlannerItem.new(day=day, bucket=bucket, text=chunk))


def mark_item_done(store, day: date, bucket: str, index: int, completed: bool = True) -> int:
    bucket_items = [item for item in store.list_day_items(day) if item.bucket == bucket]
    if index < 1 or index > len(bucket_items):
        return 1
    store.set_completed(bucket_items[index - 1].id, completed)
    return 0


def _input_with_prefill(prompt: str, initial: str) -> str:
    if not initial:
        return input(prompt)

    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind('"\\e[C": forward-char')
    readline.parse_and_bind('"\\e[D": backward-char')
    readline.parse_and_bind('"\\C-f": forward-char')
    readline.parse_and_bind('"\\C-b": backward-char')
    readline.set_startup_hook(lambda: readline.insert_text(initial))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook(None)
