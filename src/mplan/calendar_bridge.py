import json
import subprocess
from datetime import date, datetime, time, timedelta

from mplan.models import ImportedCalendarEvent, PlannerItem


class CalendarBridge:
    BUCKET_STARTS = {"早": time(8, 0), "午": time(13, 0), "晚": time(19, 0)}
    EVENT_DURATION_MINUTES = 30
    SCRIPT_TIMEOUT_SECONDS = 30
    TARGET_CALENDAR_NAME = "mplan"

    def _run_script(self, script: str) -> str:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=self.SCRIPT_TIMEOUT_SECONDS,
        )
        return result.stdout.strip()

    def owned_title_for(
        self, item: PlannerItem, completed: bool | None = None
    ) -> str:
        is_done = item.completed if completed is None else completed
        prefix = "✓ " if is_done else ""
        return f"{prefix}{item.bucket}｜{item.text}"

    def event_window_for(
        self, item: PlannerItem, order_index: int
    ) -> tuple[datetime, datetime]:
        start = datetime.combine(item.day, self.BUCKET_STARTS[item.bucket])
        start += timedelta(minutes=self.EVENT_DURATION_MINUTES * order_index)
        return start, start + timedelta(minutes=self.EVENT_DURATION_MINUTES)

    def fetch_timed_events(
        self, month_start: date, month_end: date
    ) -> list[ImportedCalendarEvent]:
        script = self._list_script(month_start, month_end)
        payload = self._run_script(script)
        records = json.loads(payload) if payload else []
        return [
            ImportedCalendarEvent(
                id=record["id"],
                title=record["title"],
                starts_at=datetime.fromisoformat(record["starts_at"]),
                ends_at=datetime.fromisoformat(record["ends_at"]),
                calendar_name=record["calendar_name"],
                notes=record.get("notes"),
            )
            for record in records
            if not record.get("all_day", False)
        ]

    def list_timed_events(
        self, month_start: date, month_end: date
    ) -> list[ImportedCalendarEvent]:
        try:
            return self.fetch_timed_events(month_start, month_end)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []

    def upsert_owned_event(self, item: PlannerItem, order_index: int) -> str:
        title = self.owned_title_for(item)
        starts_at, ends_at = self.event_window_for(item, order_index)
        metadata = json.dumps(
            {
                "source": "mplan",
                "item_id": item.id,
                "bucket": item.bucket,
                "day": item.day.isoformat(),
            },
            ensure_ascii=False,
        )
        external_event_id = item.external_event_id or ""
        script = f"""
{self._applescript_date("eventStart", starts_at)}
{self._applescript_date("eventEnd", ends_at)}
set eventTitle to "{self._escape(title)}"
set eventNotes to "{self._escape(metadata)}"
set targetEventId to "{self._escape(external_event_id)}"
tell application "Calendar"
{self._icloud_target_calendar_block()}
    set targetEvent to missing value
    set targetEventIsOwned to false
    if targetEventId is not "" then
        repeat with cal in calendars
            try
                set foundEvent to first event of cal whose uid is targetEventId
                if cal is targetCalendar then
                    set targetEvent to foundEvent
                    set targetEventIsOwned to true
                    exit repeat
                end if
            end try
        end repeat
    end if
    if targetEvent is missing value or targetEventIsOwned is false then
        set targetEvent to make new event at end of events of targetCalendar with properties {{summary:eventTitle, start date:eventStart, end date:eventEnd, description:eventNotes}}
    else
        set summary of targetEvent to eventTitle
        set start date of targetEvent to eventStart
        set end date of targetEvent to eventEnd
        set description of targetEvent to eventNotes
    end if
    return uid of targetEvent
end tell
"""
        try:
            return self._run_script(script)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ) as exc:
            raise RuntimeError(self._icloud_target_calendar_error()) from exc

    def delete_owned_event(self, event_id: str) -> None:
        script = f"""
set targetEventId to "{self._escape(event_id)}"
tell application "Calendar"
{self._icloud_target_calendar_block(create_if_missing=False)}
    if targetCalendar is missing value then return "missing"
    set targetEvent to missing value
    try
        set targetEvent to first event of events of targetCalendar whose uid is targetEventId
    end try
    if targetEvent is missing value then return "missing"
    delete targetEvent
    return "ok"
end tell
return "missing"
"""
        self._run_script(script)

    def healthcheck(self) -> tuple[bool, str]:
        try:
            result = self._run_script('tell application "Calendar" to return name')
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ) as exc:
            return False, str(exc)
        return True, result or "Calendar automation available"

    def ensure_target_calendar(self) -> str:
        script = f"""
tell application "Calendar"
{self._icloud_target_calendar_block(create_if_missing=True)}
    return "iCloud::" & name of targetCalendar
end tell
"""
        try:
            return self._run_script(script)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ) as exc:
            raise RuntimeError(self._icloud_target_calendar_error()) from exc

    def calendar_status(self) -> tuple[bool, str]:
        try:
            detail = self.ensure_target_calendar()
        except RuntimeError as exc:
            return False, str(exc)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ) as exc:
            return False, str(exc)
        return True, detail or "Calendar target available"

    def _icloud_target_calendar_block(self, create_if_missing: bool = True) -> str:
        creation_block = (
            """
    if targetCalendar is missing value then
        if nonWritableTargetCalendar is not missing value then error "{error_message}"
        if iCloudSource is missing value then error "{error_message}"
        set targetCalendar to make new calendar at end of calendars with properties {{name:targetCalendarName, container:iCloudSource}}
    end if
""".strip()
            if create_if_missing
            else ""
        )
        return f"""
    set targetCalendarName to "{self.TARGET_CALENDAR_NAME}"
    set iCloudSource to missing value
    set targetCalendar to missing value
    set nonWritableTargetCalendar to missing value
    repeat with cal in calendars
        try
            set containerName to name of its container
            if containerName contains "iCloud" then
                set iCloudSource to its container
                if name of cal is targetCalendarName and writable of cal then
                    set targetCalendar to cal
                    exit repeat
                else if name of cal is targetCalendarName then
                    set nonWritableTargetCalendar to cal
                    exit repeat
                end if
            end if
        end try
    end repeat
{creation_block.format(error_message=self._icloud_target_calendar_error()) if create_if_missing else ""}
""".strip()

    def _icloud_target_calendar_error(self) -> str:
        return "未找到可写的 iCloud 日历，请先在 Calendar.app 登录 iCloud 并启用日历同步"

    def _list_script(self, month_start: date, month_end: date) -> str:
        range_start = datetime.combine(month_start, time(0, 0, 0))
        range_end = datetime.combine(month_end, time(23, 59, 59))
        return f"""
{self._applescript_date("rangeStart", range_start)}
{self._applescript_date("rangeEnd", range_end)}
tell application "Calendar"
    set jsonParts to {{}}
    repeat with cal in calendars
        set matchingEvents to every event of cal whose start date ≥ rangeStart and start date ≤ rangeEnd
        repeat with evt in matchingEvents
            set eventJson to "{{" & ¬
                "\\"id\\":\\"" & my escape_json(uid of evt) & "\\"," & ¬
                "\\"title\\":\\"" & my escape_json(summary of evt) & "\\"," & ¬
                "\\"all_day\\":" & my bool_to_json(allday event of evt) & "," & ¬
                "\\"starts_at\\":\\"" & my iso_datetime(start date of evt) & "\\"," & ¬
                "\\"ends_at\\":\\"" & my iso_datetime(end date of evt) & "\\"," & ¬
                "\\"calendar_name\\":\\"" & my escape_json(name of cal) & "\\"," & ¬
                "\\"notes\\":" & my nullable_text(description of evt) & "}}"
            copy eventJson to end of jsonParts
        end repeat
    end repeat
    if (count of jsonParts) is 0 then return "[]"
    set AppleScript's text item delimiters to ","
    set payload to "[" & (jsonParts as text) & "]"
    set AppleScript's text item delimiters to ""
    return payload
end tell

on bool_to_json(flagValue)
    if flagValue then return "true"
    return "false"
end bool_to_json

on nullable_text(textValue)
    if textValue is missing value then return "null"
    if textValue is "" then return "null"
    return "\\"" & my escape_json(textValue) & "\\""
end nullable_text

on iso_datetime(theDate)
    set yyyy to year of theDate as integer
    set mm to text -2 thru -1 of ("0" & (month of theDate as integer))
    set dd to text -2 thru -1 of ("0" & day of theDate)
    set hh to text -2 thru -1 of ("0" & hours of theDate)
    set mi to text -2 thru -1 of ("0" & minutes of theDate)
    set ss to text -2 thru -1 of ("0" & seconds of theDate)
    return (yyyy as text) & "-" & mm & "-" & dd & "T" & hh & ":" & mi & ":" & ss
end iso_datetime

on escape_json(textValue)
    set escapedText to my replace_text(textValue, "\\\\", "\\\\\\\\")
    set escapedText to my replace_text(escapedText, "\\"", "\\\\\\"")
    set escapedText to my replace_text(escapedText, return, "\\\\n")
    set escapedText to my replace_text(escapedText, linefeed, "\\\\n")
    return escapedText
end escape_json

on replace_text(theText, searchString, replacementString)
    set AppleScript's text item delimiters to searchString
    set textItems to every text item of theText
    set AppleScript's text item delimiters to replacementString
    set theText to textItems as text
    set AppleScript's text item delimiters to ""
    return theText
end replace_text
"""

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _applescript_date(self, variable_name: str, value: datetime) -> str:
        return f"""
set {variable_name} to current date
set year of {variable_name} to {value.year}
set month of {variable_name} to {value.month}
set day of {variable_name} to {value.day}
set time of {variable_name} to ({value.hour} * hours + {value.minute} * minutes + {value.second})
""".strip()
