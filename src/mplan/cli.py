import argparse
from datetime import date

from mplan.app import run_app
from mplan.calendar_bridge import CalendarBridge
from mplan.config import default_db_path, ensure_data_dir
from mplan.day_editor import mark_item_done
from mplan.doctor import run_doctor
from mplan.models import PlannerItem
from mplan.storage import Store
from mplan.sync import SyncEngine


def launch_app() -> int:
    store = build_store()
    sync_engine = build_sync_engine(store)
    return run_app(store, sync_engine)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mplan")
    subparsers = parser.add_subparsers(dest="command")
    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("day")
    add_parser.add_argument("bucket")
    add_parser.add_argument("text")
    done_parser = subparsers.add_parser("done")
    done_parser.add_argument("day")
    done_parser.add_argument("bucket")
    done_parser.add_argument("index", type=int)
    subparsers.add_parser("sync")
    subparsers.add_parser("doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor()
    if args.command == "add":
        return handle_add(args)
    if args.command == "done":
        return handle_done(args)
    if args.command == "sync":
        return handle_sync(args)
    if args.command is None:
        return launch_app()
    return 0


def build_store() -> Store:
    ensure_data_dir()
    store = Store(default_db_path())
    store.initialize()
    return store


def build_sync_engine(store: Store) -> SyncEngine:
    return SyncEngine(store, CalendarBridge())


def local_today() -> date:
    return date.today()


def parse_mmdd(value: str, *, reference: date | None = None) -> date:
    current = reference or local_today()
    month, day = value.split("/", 1)
    return date(current.year, int(month), int(day))


def handle_add(args) -> int:
    day = parse_mmdd(args.day)
    store = build_store()
    store.upsert_planner_item(
        PlannerItem.new(day=day, bucket=args.bucket, text=args.text)
    )
    return 0


def handle_done(args) -> int:
    day = parse_mmdd(args.day)
    store = build_store()
    return mark_item_done(store, day, args.bucket, args.index, completed=True)


def handle_sync(args) -> int:
    store = build_store()
    sync_engine = build_sync_engine(store)
    today = local_today()
    try:
        report = sync_engine.sync_month(today.year, today.month)
    except Exception as exc:
        print(f"同步失败: {exc}")
        return 1
    print(
        f"已同步: 导入 {report.imported_count}，导出 {report.exported_count}，更新 {report.updated_count}"
    )
    if getattr(report, "warning", None):
        print(report.warning)
    return 0
