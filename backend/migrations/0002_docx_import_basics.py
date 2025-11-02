# backend/migrations/0002_docx_import_basics.py
from sqlalchemy import MetaData, Table, Column, String, Integer, Text, DateTime, Float
from sqlalchemy.sql import func
from sqlalchemy.engine import Engine

def upgrade(engine: Engine) -> None:
    md = MetaData()
    md.reflect(bind=engine)

    # Add columns to segments
    if "segments" in md.tables:
        seg = md.tables["segments"]
        if "paragraph_index" not in seg.c:
            with engine.begin() as conn:
                conn.exec_driver_sql("ALTER TABLE segments ADD COLUMN paragraph_index INTEGER")

    # Add columns to events
    if "events" in md.tables:
        ev = md.tables["events"]
        with engine.begin() as conn:
            if "event_kind" not in ev.c:
                conn.exec_driver_sql("ALTER TABLE events ADD COLUMN event_kind TEXT")
            if "raw_excerpt" not in ev.c:
                conn.exec_driver_sql("ALTER TABLE events ADD COLUMN raw_excerpt TEXT")

    # AI audit log
    md2 = MetaData()
    if "ai_calls" not in md.tables:
        from sqlalchemy import Table
        Table(
            "ai_calls", md2,
            Column("id", String, primary_key=True),
            Column("ts", DateTime(timezone=True), nullable=False, server_default=func.now()),
            Column("endpoint", String, nullable=False),
            Column("model", String, nullable=True),
            Column("params_json", Text, nullable=True),      # serialized params
            Column("prompt_hash", String, nullable=True),
            Column("response_id", String, nullable=True),
            Column("related_event_id", String, nullable=True),
        )
        md2.create_all(bind=engine)
