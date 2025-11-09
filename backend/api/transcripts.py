# backend/api/transcripts.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text as sql
from sqlalchemy.exc import OperationalError  # ✨ Import OperationalError
from typing import Optional, List, Dict, Any
from backend.db import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("")
def list_transcripts(q: Optional[str] = Query(None), limit: int = 200, db: Session = Depends(get_db)):
    
    # Try to execute the query.
    try:
        if q:
            rows = db.execute(sql("""
              SELECT transcript_id AS id, title, notes, n_segments, n_events, n_proposed, n_accepted
              FROM v_transcript_stats
              WHERE (title LIKE :q OR notes LIKE :q OR transcript_id LIKE :q)
              ORDER BY n_events DESC LIMIT :lim
            """), {"q": f"%{q}%", "lim": limit}).mappings().all()
        else:
            rows = db.execute(sql("""
              SELECT transcript_id AS id, title, notes, n_segments, n_events, n_proposed, n_accepted
              FROM v_transcript_stats
              ORDER BY updated_at DESC, transcript_id ASC LIMIT :lim
            """), {"lim": limit}).mappings().all()
        
        return [dict(r) for r in rows]

    # ✅ FIX: If the query fails (e.g., table/view doesn't exist), return an empty list.
    except OperationalError:
        return []