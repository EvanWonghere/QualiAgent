# backend/migrations/0004_irr.py
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

def upgrade(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(sql("""
        CREATE TABLE IF NOT EXISTS irr_tasks (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          item_type TEXT NOT NULL,         -- 'event' | 'segment'
          scope_transcript_id TEXT,        -- optional filter
          source TEXT NOT NULL,            -- for events: 'proposed'|'accepted'; for segments: 'all'
          sample_size INTEGER NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""))
        conn.execute(sql("""
        CREATE TABLE IF NOT EXISTS irr_items (
          id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          item_type TEXT NOT NULL,         -- 'event'|'segment'
          item_id TEXT NOT NULL,           -- events.id or segments.id
          FOREIGN KEY(task_id) REFERENCES irr_tasks(id) ON DELETE CASCADE
        )"""))
        conn.execute(sql("""
        CREATE TABLE IF NOT EXISTS irr_judgments (
          id TEXT PRIMARY KEY,
          task_id TEXT NOT NULL,
          item_id TEXT NOT NULL,           -- refers to irr_items.item_id
          coder_id TEXT NOT NULL,
          decision TEXT,                   -- e.g., 'accept'|'reject' (for events)
          codebook_id TEXT,                -- single-label nominal (optional)
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""))
