import subprocess
from dataclasses import replace
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
        lambda script: (
            captured.setdefault("script", script),
            '{"event_id":"event-1","deleted_event_id":null}',
        )[1],
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
        lambda script: (
            captured.setdefault("script", script),
            '{"event_id":"evt-123","deleted_event_id":null}',
        )[1],
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
        lambda script: (
            captured.setdefault("script", script),
            '{"event_id":"evt-123","deleted_event_id":null}',
        )[1],
    )

    bridge.upsert_owned_event(item, order_index=1)
    assert "set sourceEventToDelete to missing value" in captured["script"]
    assert "if cal is targetCalendar" in captured["script"]
    assert "notes_identify_mplan" in captured["script"]


def test_upsert_only_migrates_owned_events_from_writable_source_calendars(monkeypatch):
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
        external_event_id="read-only-evt-123",
    )
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (
            captured.setdefault("script", script),
            '{"event_id":"icloud-evt-123","deleted_event_id":null}',
        )[1],
    )

    bridge.upsert_owned_event(item, order_index=1)

    assert "if writable of cal and my notes_identify_mplan(description of foundEvent) then" in captured["script"]
    assert "delete sourceEventToDelete" in captured["script"]


def test_delete_targets_calendar_event(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "ok")[1],
    )

    bridge.delete_owned_event("evt-456")
    assert 'tell application "Calendar"' in captured["script"]
    assert "evt-456" in captured["script"]


def test_delete_only_targets_event_in_resolved_calendar(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "ok")[1],
    )

    bridge.delete_owned_event("evt-456")
    assert 'set targetCalendarName to "mplan"' in captured["script"]
    assert "first event of targetCalendar whose uid is targetEventId" in captured["script"]
    assert "first event of events of targetCalendar" not in captured["script"]
    assert "delete targetEvent" in captured["script"]


def test_delete_owned_event_raises_when_calendar_event_is_missing(monkeypatch):
    bridge = CalendarBridge()
    monkeypatch.setattr(bridge, "_run_script", lambda script: "missing")

    try:
        bridge.delete_owned_event("evt-missing")
    except RuntimeError as exc:
        assert "未找到" in str(exc)
    else:
        raise AssertionError("expected missing Calendar event to fail deletion")


def test_delete_owned_event_accepts_explicit_ok(monkeypatch):
    bridge = CalendarBridge()
    monkeypatch.setattr(bridge, "_run_script", lambda script: "ok")

    bridge.delete_owned_event("evt-456")


def test_ensure_target_calendar_uses_existing_mplan_calendar(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "Calendar::mplan")[1],
    )

    assert bridge.ensure_target_calendar() == "Calendar::mplan"
    assert 'set targetCalendarName to "mplan"' in captured["script"]
    assert "if name of cal is targetCalendarName then" in captured["script"]
    assert "container" not in captured["script"]


def test_ensure_target_calendar_errors_when_mplan_calendar_is_missing(monkeypatch):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "Calendar::mplan")[1],
    )

    assert bridge.ensure_target_calendar() == "Calendar::mplan"
    assert "error " in captured["script"]
    assert "create calendar" not in captured["script"]
    assert "make new calendar" not in captured["script"]
    assert "iCloudSource" not in captured["script"]


def test_ensure_target_calendar_errors_when_existing_icloud_mplan_is_not_writable(
    monkeypatch,
):
    bridge = CalendarBridge()
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), "Calendar::mplan")[1],
    )

    assert bridge.ensure_target_calendar() == "Calendar::mplan"
    assert "set nonWritableTargetCalendar to cal" in captured["script"]
    assert "if nonWritableTargetCalendar is not missing value then error" in captured[
        "script"
    ]
    assert "create calendar" not in captured["script"]


def test_upsert_owned_event_targets_icloud_mplan_calendar(monkeypatch):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文")
    captured = {}
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: (captured.setdefault("script", script), '{"event_id":"evt-1","deleted_event_id":null}')[1],
    )

    assert bridge.upsert_owned_event(item, order_index=0) == ("evt-1", None)
    assert 'set targetCalendarName to "mplan"' in captured["script"]
    assert "item 1 of writableCalendars" not in captured["script"]
    assert "create calendar" not in captured["script"]
    assert "on escape_json(textValue)" in captured["script"]
    assert "on replace_text(theText, searchString, replacementString)" in captured["script"]


def test_upsert_owned_event_returns_new_uid_and_old_uid_for_local_migration(
    monkeypatch,
):
    bridge = CalendarBridge()
    item = PlannerItem.new(day=date(2026, 7, 12), bucket="午", text="改简历")
    item = replace(item, external_event_id="local-evt-1")
    monkeypatch.setattr(
        bridge,
        "_run_script",
        lambda script: '{"event_id":"icloud-evt-1","deleted_event_id":"local-evt-1"}',
    )

    event_id, deleted_event_id = bridge.upsert_owned_event(item, order_index=0)

    assert event_id == "icloud-evt-1"
    assert deleted_event_id == "local-evt-1"


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
        match="无法写入 mplan 日历",
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
    assert detail.startswith("无法写入 mplan 日历")


def test_calendar_status_explains_missing_calendars_automation_permission(monkeypatch):
    bridge = CalendarBridge()

    def raise_called_process_error(script):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["osascript"],
            output="",
            stderr='177:186: execution error: 变量“calendars”没有定义。 (-2753)',
        )

    monkeypatch.setattr(bridge, "_run_script", raise_called_process_error)

    ok, detail = bridge.calendar_status()

    assert ok is False
    assert "Calendar.app 自动化无法读取日历列表" in detail
    assert "访问日历和自动化" in detail


def test_upsert_explains_calendar_dictionary_compile_failure(monkeypatch):
    bridge = CalendarBridge()

    def raise_called_process_error(script):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["osascript"],
            output="",
            stderr="27:31: syntax error: 预期是行的结尾等等，却找到类名称。 (-2741)",
        )

    monkeypatch.setattr(bridge, "_run_script", raise_called_process_error)

    with pytest.raises(RuntimeError, match="Calendar.app 自动化无法读取日历列表"):
        bridge.upsert_owned_event(
            PlannerItem.new(day=date(2026, 7, 12), bucket="早", text="看论文"),
            order_index=0,
        )


def test_calendar_status_reports_calendar_target(monkeypatch):
    bridge = CalendarBridge()
    monkeypatch.setattr(bridge, "_run_script", lambda script: "Calendar::mplan")

    ok, detail = bridge.calendar_status()

    assert ok is True
    assert detail == "Calendar::mplan"
