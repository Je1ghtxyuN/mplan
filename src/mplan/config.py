from pathlib import Path


def default_data_dir() -> Path:
    return Path.home() / ".mplan"


def default_db_path() -> Path:
    return default_data_dir() / "mplan.db"


def ensure_data_dir() -> Path:
    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
