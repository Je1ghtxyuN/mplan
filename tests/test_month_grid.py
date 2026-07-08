from datetime import date

from mplan.month_grid import DayCell, render_day_cell


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
