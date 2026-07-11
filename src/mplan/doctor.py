from mplan.calendar_bridge import CalendarBridge
from mplan.config import default_data_dir, default_db_path


def run_doctor() -> int:
    bridge = CalendarBridge()
    ok, detail = bridge.healthcheck()
    target_ok, target_detail = bridge.calendar_status()
    print(f"Data dir: {default_data_dir()}")
    print(f"Database: {default_db_path()}")
    print("Calendar:", "ok" if ok else "error")
    print(detail)
    print("Target calendar:", target_detail if target_ok else f"error: {target_detail}")
    return 0 if ok and target_ok else 1
