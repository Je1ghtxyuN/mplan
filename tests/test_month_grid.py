from datetime import date

from mplan.month_grid import DayCell, DayViewModel, build_month_grid, render_day_cell


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
    assert lines[0].startswith("+")
    assert any("[1]" in line for line in lines)
    assert any("(其他月)" in line for line in lines)


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
    assert all(len(line) == 22 for line in lines)
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
    assert lines[-2].strip("| ").startswith("...")
