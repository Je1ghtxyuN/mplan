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
    assert lines[0].startswith("[")
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
