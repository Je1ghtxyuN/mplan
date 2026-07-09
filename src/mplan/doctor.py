from mplan.calendar_bridge import CalendarBridge
from mplan.config import default_data_dir, default_db_path


def run_doctor() -> int:
    bridge = CalendarBridge()
    ok, detail = bridge.healthcheck()
    print(f"Data dir: {default_data_dir()}")
    print(f"Database: {default_db_path()}")
    print("Calendar:", "ok" if ok else "error")
    print(detail)
    return 0 if ok else 1
