# backend/migrations/0005_transcripts.py
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

def upgrade(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(sql("""
        CREATE TABLE IF NOT EXISTS transcripts (
          id TEXT PRIMARY KEY,
          title TEXT,
          notes TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""))
        conn.execute(sql("""
        CREATE TABLE IF NOT EXISTS transcript_stats (
          transcript_id TEXT PRIMARY KEY,
          n_segments INTEGER DEFAULT 0,
          n_events INTEGER DEFAULT 0,
          n_proposed INTEGER DEFAULT 0,
          n_accepted INTEGER DEFAULT 0,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
        )"""))
        # Idempotent helper view (optional)
        conn.execute(sql("""
        CREATE VIEW IF NOT EXISTS v_transcript_stats AS
        SELECT t.id AS transcript_id, t.title, t.notes,
               COALESCE(ts.n_segments,0) n_segments,
               COALESCE(ts.n_events,0)   n_events,
               COALESCE(ts.n_proposed,0) n_proposed,
               COALESCE(ts.n_accepted,0) n_accepted
        FROM transcripts t
        LEFT JOIN transcript_stats ts ON ts.transcript_id=t.id
        """))
