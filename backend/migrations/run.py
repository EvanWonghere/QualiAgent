# backend/migrations/run.py
from __future__ import annotations
import importlib
from typing import Callable, List
from sqlalchemy.engine import Engine
from backend.db import engine, db_info

MIGRATIONS: List[str] = [
    "backend.migrations.0001_init_v2",
    "backend.migrations.0002_docx_import_basics",
    "backend.migrations.0003_indexes",
    "backend.migrations.0004_irr",
    "backend.migrations.0005_transcripts",
]

def _load_mod(name: str):
    mod = importlib.import_module(name)
    if not hasattr(mod, "upgrade"):
        raise RuntimeError(f"{name} missing upgrade(engine) function")
    return mod

def run(engine_obj: Engine | None = None) -> None:
    eng = engine_obj or engine  # <- reuse the app engine
    print("=== QualiAgent Migration Runner ===")
    print("DB file:", db_info())
    with eng.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    for name in MIGRATIONS:
        print("Running migration:", name.split(".")[-1])
        mod = _load_mod(name)
        mod.upgrade(eng)
    print("Migration complete.")

if __name__ == "__main__":
    run()
