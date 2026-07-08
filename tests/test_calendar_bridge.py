from datetime import date

from mplan.calendar_bridge import CalendarBridge
from mplan.models import PlannerItem


def test_list_timed_events_filters_all_day_events(monkeypatch):
    bridge = CalendarBridge()
    payload = (
        '[{"id":"1","title":"腾讯会议","all_day":false,"starts_at":"2026-07-01T09:00:00",'
        '"ends_at":"2026-07-01T10:00:00","calendar_name":"工作","notes":"link"},'
        '{"id":"2","title":"生日","all_day":true,"starts_at":"2026-07-01T00:00:00",'
        '"ends_at":"2026-07-01T23:59:00","calendar_name":"订阅","notes":null}]'
    )
    monkeypatch.setattr(bridge, "_run_script", lambda script: payload)

    events = bridge.list_timed_events(date(2026, 7, 1), date(2026, 7, 31))
    assert [event.title for event in events] == ["腾讯会议"]


def test_owned_event_title_includes_completion_prefix(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文").with_completed(True)
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: captured.setdefault("script", script) or "event-1",
    )

    bridge.upsert_owned_event(item, order_index=0)
    assert "✓ 早｜看论文" in captured["script"]
