from datetime import date, datetime

from mplan.detail_view import _display_width, build_detail_view
from mplan.models import ImportedCalendarEvent, PlannerItem


def test_build_detail_view_shows_full_day_sections_and_active_bucket():
    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="午",
        imported_events=[
            ImportedCalendarEvent(
                id="evt-1",
                title="腾讯会议",
                starts_at=datetime.fromisoformat("2026-07-10T09:00:00"),
                ends_at=datetime.fromisoformat("2026-07-10T10:00:00"),
                calendar_name="工作",
            )
        ],
        bucket_items={
            "早": [PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="看论文")],
            "午": [PlannerItem.new(day=date(2026, 7, 10), bucket="午", text="改简历")],
            "晚": [],
        },
        selected_task_index=None,
        width=60,
        height=16,
    )

    assert any("2026-07-10" in row for row in rows)
    assert any("正式日程" in row for row in rows)
    assert any("> 午" in row or ">午" in row for row in rows)
    assert any("改简历" in row for row in rows)


def test_build_detail_view_marks_selected_local_task_and_completion():
    completed = PlannerItem.new(
        day=date(2026, 7, 10), bucket="午", text="改简历"
    ).with_completed(True)

    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="午",
        imported_events=[],
        bucket_items={"早": [], "午": [completed], "晚": []},
        selected_task_index=0,
        width=60,
        height=16,
    )

    assert any("> ✓ 改简历" in row for row in rows)


def test_build_detail_view_keeps_right_border_aligned_for_cjk_text():
    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="早",
        imported_events=[],
        bucket_items={
            "早": [PlannerItem.new(day=date(2026, 7, 10), bucket="早", text="一段很长的中文任务")],
            "午": [],
            "晚": [],
        },
        selected_task_index=0,
        width=61,
        height=16,
    )

    panel_rows = [row for row in rows if "║" in row or "╔" in row or "╚" in row]
    assert panel_rows
    assert len({_display_width(row.rstrip()) for row in panel_rows}) == 1


def test_build_detail_view_scrolls_to_keep_selected_task_visible():
    tasks = [
        PlannerItem.new(day=date(2026, 7, 10), bucket="早", text=f"任务{index}")
        for index in range(12)
    ]

    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="早",
        imported_events=[],
        bucket_items={"早": tasks, "午": [], "晚": []},
        selected_task_index=11,
        width=50,
        height=10,
    )

    assert any("> 任务11" in row for row in rows)


def test_build_detail_view_stays_inside_small_terminal_dimensions():
    rows = build_detail_view(
        day=date(2026, 7, 10),
        bucket="早",
        imported_events=[],
        bucket_items={"早": [], "午": [], "晚": []},
        selected_task_index=0,
        width=20,
        height=8,
    )

    assert len(rows) == 8
    assert all(_display_width(row) == 20 for row in rows)
    assert any("╗" in row for row in rows)
    assert any("╝" in row for row in rows)
