import argparse


def launch_app() -> int:
    return 0


def run_doctor() -> int:
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mplan")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("add")
    subparsers.add_parser("done")
    subparsers.add_parser("sync")
    subparsers.add_parser("doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor()
    if args.command is None:
        return launch_app()
    return 0
