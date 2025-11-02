# backend/migrations/0003_indexes.py
from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

def upgrade(engine: Engine) -> None:
    stmts = [
        "CREATE INDEX IF NOT EXISTS ix_events_status ON events(status)",
        "CREATE INDEX IF NOT EXISTS ix_events_created_by ON events(created_by)",
        "CREATE INDEX IF NOT EXISTS ix_event_labels_event ON event_labels(event_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_labels_codebook ON event_labels(codebook_id)",
        "CREATE INDEX IF NOT EXISTS ix_codebook_status ON codebook(status)",
        "CREATE INDEX IF NOT EXISTS ix_segments_tx_idx ON segments(transcript_id, [index])",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(sql(s))
