from datetime import date

from mplan.tui_state import (
    TuiState,
    cycle_bucket,
    enter_insert_mode,
    exit_insert_mode,
    parse_bucket_text,
    serialize_bucket_text,
)


def test_cycle_bucket_wraps_forward_and_backward():
    assert cycle_bucket("早") == "午"
    assert cycle_bucket("晚") == "早"
    assert cycle_bucket("早", reverse=True) == "晚"


def test_enter_insert_mode_sets_mode_and_buffer():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    updated = enter_insert_mode(state, "看论文 | 回消息")
    assert updated.mode == "INSERT"
    assert updated.edit_buffer == "看论文 | 回消息"


def test_exit_insert_mode_clears_buffer_and_sets_status():
    state = TuiState.initial(selected_day=date(2026, 7, 12))
    editing = enter_insert_mode(state, "看论文")
    updated = exit_insert_mode(editing, "已保存")
    assert updated.mode == "NORMAL"
    assert updated.edit_buffer == ""
    assert updated.status_message == "已保存"


def test_bucket_text_round_trip_trims_and_drops_empty_segments():
    assert parse_bucket_text(" 看论文 |  | 回消息 | ") == ["看论文", "回消息"]
    assert serialize_bucket_text(["看论文", "回消息"]) == "看论文 | 回消息"
