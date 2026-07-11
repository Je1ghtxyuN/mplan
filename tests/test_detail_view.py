from datetime import date, datetime

from mplan.detail_view import build_detail_view
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
