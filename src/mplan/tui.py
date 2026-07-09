from __future__ import annotations

import curses
from dataclasses import replace
from datetime import date
from importlib import import_module
from typing import Any

from mplan.tui_state import (
    TuiState,
    cycle_bucket,
    enter_insert_mode,
    exit_insert_mode,
    move_selection,
)
from mplan.tui_store import load_bucket_text, save_bucket_text


def handle_keypress(
    state: TuiState,
    key: int,
    store,
    sync_engine,
) -> tuple[TuiState, bool]:
    if state.mode == "NORMAL":
        if key == ord("q"):
            return state, True
        if key == ord("\t"):
            return replace(
                state,
                selected_bucket=cycle_bucket(state.selected_bucket),
            ), False
        if key == ord("i"):
            return enter_insert_mode(
                state,
                load_bucket_text(store, state.selected_day, state.selected_bucket),
            ), False
        if key == ord("s"):
            report = sync_engine.sync_month(state.visible_year, state.visible_month)
            status = (
                f"已同步: 导入 {report.imported_count}，"
                f"导出 {report.exported_count}，更新 {report.updated_count}"
            )
            if report.warning:
                status = f"{status} {report.warning}"
            return replace(state, status_message=status), False

        arrow_map = {
            curses.KEY_LEFT: "left",
            curses.KEY_RIGHT: "right",
            curses.KEY_UP: "up",
            curses.KEY_DOWN: "down",
        }
        if key in arrow_map:
            return move_selection(state, arrow_map[key]), False
        return state, False

    if key == 27:
        save_bucket_text(store, state.selected_day, state.selected_bucket, state.edit_buffer)
        return exit_insert_mode(state, "已保存"), False
    if key in (curses.KEY_BACKSPACE, 127):
        return replace(state, edit_buffer=state.edit_buffer[:-1]), False
    if key == curses.KEY_ENTER:
        return replace(state, edit_buffer=f"{state.edit_buffer}\n"), False
    if 32 <= key <= 126 or key > 127:
        return replace(state, edit_buffer=f"{state.edit_buffer}{chr(key)}"), False
    return state, False


def run_tui(store, sync_engine) -> int:
    def _main(stdscr) -> int:
        state = TuiState.initial(selected_day=date.today())
        while True:
            _draw_screen(stdscr, store, sync_engine, state)
            key = stdscr.getch()
            state, should_quit = handle_keypress(state, key, store, sync_engine)
            if should_quit:
                return 0

    return curses.wrapper(_main)


def _draw_screen(stdscr, store, sync_engine, state: TuiState) -> None:
    build_screen_view = _load_build_screen_view()
    height, width = stdscr.getmaxyx()
    view = build_screen_view(
        store,
        sync_engine,
        state,
        width=width,
        height=height,
    )

    stdscr.clear()
    lines = _view_to_lines(view)
    for row, line in enumerate(lines[:height]):
        stdscr.addnstr(row, 0, line, max(0, width - 1))
    stdscr.refresh()


def _load_build_screen_view():
    module = import_module("mplan.tui_render")
    return module.build_screen_view


def _view_to_lines(view: dict[str, Any]) -> list[str]:
    lines: list[str] = [str(view.get("header", ""))]

    body = view.get("body")
    if isinstance(body, list):
        lines.extend(str(line) for line in body)
    elif isinstance(body, str):
        lines.extend(body.splitlines())

    if "editor_text" in view:
        lines.append(str(view["editor_text"]))
    lines.append(str(view.get("footer", "")))
    return lines
