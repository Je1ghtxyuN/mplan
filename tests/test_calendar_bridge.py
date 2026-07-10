import subprocess
from datetime import date

import pytest

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
    assert 'tell application "Calendar"' in captured["script"]


def test_list_script_targets_calendar_and_month_bounds():
    bridge = CalendarBridge()

    script = bridge._list_script(date(2026, 7, 1), date(2026, 7, 31))
    assert 'tell application "Calendar"' in script
    assert "set year of rangeStart to 2026" in script
    assert "set month of rangeStart to 7" in script
    assert "set day of rangeStart to 1" in script
    assert "set day of rangeEnd to 31" in script


def test_upsert_uses_existing_event_id_when_present(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料")
    item = PlannerItem(
        id=item.id,
        day=item.day,
        bucket=item.bucket,
        text=item.text,
        completed=item.completed,
        created_at=item.created_at,
        updated_at=item.updated_at,
        external_event_id="evt-123",
    )
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: captured.setdefault("script", script) or "evt-123",
    )

    bridge.upsert_owned_event(item, order_index=1)
    assert "evt-123" in captured["script"]


def test_upsert_does_not_rewrite_unrelated_external_event(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="晚", text="整理材料")
    item = PlannerItem(
        id=item.id,
        day=item.day,
        bucket=item.bucket,
        text=item.text,
        completed=item.completed,
        created_at=item.created_at,
        updated_at=item.updated_at,
        external_event_id="evt-123",
    )
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "evt-123")[1],
    )

    bridge.upsert_owned_event(item, order_index=1)
    assert "targetEventIsOwned" in captured["script"]
    assert "set foundEventNotes to description of foundEvent" in captured["script"]
    assert "if foundEventNotes is not missing value" in captured["script"]
    assert "set foundEventContainer to container of cal" in captured["script"]
    assert "if foundEventContainer is container of targetCalendar" in captured["script"]


def test_delete_targets_calendar_event(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: captured.setdefault("script", script) or "ok",
    )

    bridge.delete_owned_event("evt-456")
    assert 'tell application "Calendar"' in captured["script"]
    assert "evt-456" in captured["script"]


def test_ensure_target_calendar_uses_existing_icloud_mplan(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "iCloud::mplan")[1],
    )

    assert bridge.ensure_target_calendar() == "iCloud::mplan"
    assert 'set targetCalendarName to "mplan"' in captured["script"]
    assert "iCloud" in captured["script"]


def test_ensure_target_calendar_creates_icloud_mplan_when_missing(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "iCloud::mplan")[1],
    )

    assert bridge.ensure_target_calendar() == "iCloud::mplan"
    assert (
        'set targetCalendar to make new calendar at end of calendars with properties {name:targetCalendarName, container:iCloudSource}'
        in captured["script"]
    )
    assert 'if iCloudSource is missing value then error "未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步"' in captured["script"]


def test_upsert_owned_event_targets_icloud_mplan_calendar(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "evt-1")[1],
    )

    assert bridge.upsert_owned_event(item, order_index=0) == "evt-1"
    assert 'set targetCalendarName to "mplan"' in captured["script"]
    assert "item 1 of writableCalendars" not in captured["script"]
    assert (
        'make new calendar at end of calendars with properties {name:targetCalendarName, container:iCloudSource}'
        in captured["script"]
    )


def test_upsert_owned_event_surfaces_explicit_icloud_failure(monkeypatch):
    bridge = CalendarBridge()

    def raise_called_process_error(script):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["osascript"],
            output="",
            stderr="No writable iCloud calendars",
        )

    monkeypatch.setattr(bridge, "_run_script", raise_called_process_error)

    with pytest.raises(
        RuntimeError,
        match="未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步",
    ):
        bridge.upsert_owned_event(
            PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文"),
            order_index=0,
        )


def test_calendar_status_reports_explicit_icloud_failure(monkeypatch):
    bridge = CalendarBridge()

    def raise_called_process_error(script):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["osascript"],
            output="",
            stderr="No writable iCloud calendars",
        )

    monkeypatch.setattr(bridge, "_run_script", raise_called_process_error)

    ok, detail = bridge.calendar_status()

    assert ok is False
    assert detail == "未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步"


def test_calendar_status_reports_icloud_target(monkeypatch):
    bridge = CalendarBridge()
    monkeypatch.setattr(bridge, "_run_script", lambda script: "iCloud::mplan")

    ok, detail = bridge.calendar_status()

    assert ok is True
    assert detail == "iCloud::mplan"
