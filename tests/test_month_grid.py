from datetime import date

from mplan.month_grid import (
    DayCell,
    DayViewModel,
    _display_width,
    build_month_grid,
    render_day_cell,
)


def test_render_day_cell_keeps_events_and_planner_sections_separate():
    cell = DayCell(
        day=date(2026, 7, 12),
        imported_events=["09:00 腾讯会议"],
        morning=["看论文"],
        afternoon=[],
        evening=["✓ 整理材料"],
        in_month=True,
        selected=False,
    )

    lines = render_day_cell(cell, width=20, height=10)
    assert any("正式" in line for line in lines)
    assert any("早:" in line for line in lines)
    assert any("晚:" in line for line in lines)
    assert any("✓ 整理材料" in line for line in lines)


def test_render_day_cell_marks_selected_and_out_of_month_days():
    cell = DayCell(
        day=date(2026, 8, 1),
        imported_events=[],
        morning=[],
        afternoon=[],
        evening=[],
        in_month=False,
        selected=True,
    )

    lines = render_day_cell(cell, width=20, height=8)
    assert any("[1]" in line for line in lines)
    assert any("(其他月)" in line for line in lines)


def test_render_day_cell_marks_selected_bucket_inside_selected_day():
    cell = DayCell(
        day=date(2026, 7, 10),
        imported_events=[],
        morning=["看论文"],
        afternoon=["改简历"],
        evening=[],
        in_month=True,
        selected=True,
        selected_bucket="午",
    )

    lines = render_day_cell(cell, width=20, height=8)
    assert any(">午:" in line for line in lines)


def test_build_month_grid_creates_calendar_rows():
    grid = build_month_grid(
        2026,
        7,
        selected_day=date(2026, 7, 12),
        day_data={
            date(2026, 7, 12): DayViewModel(
                imported_events=["09:00 腾讯会议"],
                morning=["看论文"],
                afternoon=["改简历"],
                evening=["✓ 整理材料"],
            )
        },
    )

    assert grid.year == 2026
    assert grid.month == 7
    assert len(grid.weeks) >= 4
    selected = next(cell for week in grid.weeks for cell in week if cell.selected)
    assert selected.day == date(2026, 7, 12)
    assert selected.imported_events == ["09:00 腾讯会议"]
    assert selected.afternoon == ["改简历"]


def test_build_month_grid_marks_selected_bucket_on_selected_day():
    grid = build_month_grid(
        2026,
        7,
        selected_day=date(2026, 7, 12),
        selected_bucket="午",
        day_data={
            date(2026, 7, 12): DayViewModel(
                imported_events=[],
                morning=["看论文"],
                afternoon=["改简历"],
                evening=[],
            )
        },
    )
    selected = next(cell for week in grid.weeks for cell in week if cell.selected)
    assert selected.selected_bucket == "午"


def test_build_month_grid_does_not_mark_bucket_on_unselected_days():
    grid = build_month_grid(
        2026,
        7,
        selected_day=date(2026, 7, 12),
        selected_bucket="晚",
        day_data={},
    )
    other = next(
        cell for week in grid.weeks for cell in week if cell.day == date(2026, 7, 13)
    )
    assert other.selected_bucket is None


def test_render_day_cell_wraps_long_text_without_overflow():
    cell = DayCell(
        day=date(2026, 7, 12),
        imported_events=["21:00 成田T2-香港T1-国泰 特别长的航班说明"],
        morning=["修改一段非常非常长的简历描述内容用于测试自动换行"],
        afternoon=[],
        evening=[],
        in_month=True,
        selected=False,
    )

    lines = render_day_cell(cell, width=22, height=10)
    assert len(lines) == 10
    assert all(_display_width(line) == 22 for line in lines)
    assert any("成田T2-香港T1" in line for line in lines)
    assert any("修改一段非常非常长" in line for line in lines)


def test_render_day_cell_shows_overflow_hint_when_space_runs_out():
    cell = DayCell(
        day=date(2026, 7, 12),
        imported_events=["活动说明一", "活动说明二", "活动说明三"],
        morning=["早计划一", "早计划二", "早计划三"],
        afternoon=["午计划一", "午计划二"],
        evening=["晚计划一", "晚计划二"],
        in_month=True,
        selected=False,
    )

    lines = render_day_cell(cell, width=18, height=8)
    assert lines[-1].strip() == "..."
    assert "v 12" not in lines[-1]


def test_render_day_cell_uses_display_width_for_cjk_alignment():
    cell = DayCell(
        day=date(2026, 7, 30),
        imported_events=["22:20 白云T3-香港T1-国泰"],
        morning=["制作简历"],
        afternoon=["看HappyLLM并做笔记"],
        evening=["修改ACM ISS论文"],
        in_month=True,
        selected=False,
    )

    lines = render_day_cell(cell, width=16, height=8)
    assert all(_display_width(line) == 16 for line in lines)
