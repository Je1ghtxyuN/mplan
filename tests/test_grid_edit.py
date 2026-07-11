from datetime import date

from mplan.grid_edit import (
    build_statusline,
    colorize_mode_label,
    COMMAND_ALIASES,
    create_bucket_task,
    cycle_bucket,
    load_bucket_items,
    parse_command,
    parse_bucket_buffer,
    serialize_bucket_items,
    update_bucket_task,
)
from mplan.models import PlannerItem
from mplan.storage import Store


def test_cycle_bucket_wraps_through_three_buckets():
    assert cycle_bucket("早") == "午"
    assert cycle_bucket("午") == "晚"
    assert cycle_bucket("晚") == "早"


def test_buffer_round_trip_uses_pipe_separator():
    assert serialize_bucket_items(["看论文", "回消息"]) == "看论文 | 回消息"
    assert parse_bucket_buffer(" 看论文 |  | 回消息 ") == ["看论文", "回消息"]


def test_statusline_uses_mode_first_nvim_like_text():
    line = build_statusline("NORMAL", date(2026, 7, 10), "午", "已保存")

    assert "NORMAL" in line
    assert "2026-07-10" in line
    assert "午" in line
    assert "已保存" in line


def test_create_bucket_task_adds_one_item_without_touching_existing_siblings(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧任务"))

    create_bucket_task(store, date(2026, 7, 10), "午", "新任务")

    items = store.list_bucket_items(date(2026, 7, 10), "午")
    assert [item.text for item in items] == ["旧任务", "新任务"]


def test_update_bucket_task_keeps_same_item_id(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    item = store.create_planner_item(
        PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="旧任务")
    )

    updated = update_bucket_task(store, item, "新任务")

    assert updated.id == item.id
    assert store.list_bucket_items(date(2026, 7, 10), "午")[0].text == "新任务"


def test_build_statusline_supports_command_mode_text():
    line = build_statusline("COMMAND", date(2026, 7, 10), "午", "", buffer=":sq")

    assert "COMMAND" in line
    assert ":sq" in line


def test_parse_command_normalizes_short_and_long_aliases():
    assert parse_command(":s") == "sync"
    assert parse_command(":sync") == "sync"
    assert parse_command(":sq") == "syncquit"
    assert parse_command(":v") == "view"
    assert COMMAND_ALIASES["q"] == "quit"


def test_colorize_mode_label_wraps_normal_in_ansi_codes():
    label = colorize_mode_label("NORMAL")

    assert label.startswith("\x1b[")
    assert "NORMAL" in label
    assert label.endswith("\x1b[0m")


def test_load_bucket_items_returns_bucket_planner_items(tmp_path):
    store = Store(tmp_path / "mplan.db")
    store.initialize()
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历"))
    store.create_planner_item(PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="练口语"))

    items = load_bucket_items(store, date(2026, 7, 10), "午")

    assert [item.text for item in items] == ["改简历", "练口语"]
