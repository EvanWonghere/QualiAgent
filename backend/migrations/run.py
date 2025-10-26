# backend/migrations/run.py
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

# Import your engine
from backend.db import engine  # must expose a SQLAlchemy Engine


def load_migration(module_name: str) -> Callable[[Engine], None]:
    mod = importlib.import_module(module_name)
    if not hasattr(mod, "upgrade"):
        raise RuntimeError(f"Migration module {module_name} has no 'upgrade' function")
    return getattr(mod, "upgrade")


def list_tables(e: Engine) -> list[str]:
    insp = inspect(e)
    try:
        return sorted(insp.get_table_names())
    except Exception:  # if DB not initialized or corrupt
        return []


def run():
    """
    Phase 0.5 migration runner:
    - runs 0001_init_v2.upgrade(engine)
    """
    print("=== QualiAgent Migration Runner ===")
    print("DB URL:", engine.url)

    before = list_tables(engine)
    print("Existing tables (before):", before)

    print("Running migration: backend.migrations.0001_init_v2")
    upgrade = load_migration("backend.migrations.0001_init_v2")
    upgrade(engine)

    after = list_tables(engine)
    print("Existing tables (after):", after)

    created = [t for t in after if t not in before]
    print("Newly created tables:", created if created else "None")
    print("Migration complete.")


if __name__ == "__main__":
    run()
