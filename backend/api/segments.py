# backend/api/segments.py
from __future__ import annotations
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text as sql
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.contracts.models import Segment

router = APIRouter()

# ---- DB session dependency ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- Internal helpers ----
def _select_segments(db: Session, transcript_id: str) -> List[Dict[str, Any]]:
    """
    Try a wide SELECT (including paragraph_index); if the column doesn't exist,
    fall back to a minimal SELECT. Always alias [index] -> "index".
    """
    rows: List[Dict[str, Any]] = []
    # First attempt: include paragraph_index if present
    try:
        q = """
        SELECT
            id,
            transcript_id,
            [index] AS "index",
            speaker,
            text,
            start_char,
            end_char,
            paragraph_index
        FROM segments
        WHERE transcript_id = :tid
        ORDER BY [index] ASC
        """
        rows = [dict(r) for r in db.execute(sql(q), {"tid": transcript_id}).mappings().all()]
        return rows
    except Exception:
        # Fallback: older DB without paragraph_index column
        q2 = """
        SELECT
            id,
            transcript_id,
            [index] AS "index",
            speaker,
            text,
            start_char,
            end_char
        FROM segments
        WHERE transcript_id = :tid
        ORDER BY [index] ASC
        """
        rows = [dict(r) for r in db.execute(sql(q2), {"tid": transcript_id}).mappings().all()]
        return rows

def _as_segment_models(rows: List[Dict[str, Any]]) -> List[Segment]:
    out: List[Segment] = []
    for r in rows:
        # Only pass fields the Pydantic contract expects
        data = {
            "id": str(r.get("id")),
            "transcript_id": str(r.get("transcript_id")),
            "index": int(r.get("index")),
            "text": r.get("text") or "",
            "speaker": r.get("speaker"),
            "start_char": r.get("start_char"),
            "end_char": r.get("end_char"),
        }
        out.append(Segment(**data))
    return out

def _load_from_fixtures(transcript_id: str) -> List[Segment]:
    """
    Optional fixtures fallback (Phase 0.5/0.6). If the repo is absent or raises,
    return an empty list so the caller can 404.
    """
    try:
        from backend.repositories.fixtures_repo import load_segments as load_fix
        fix = load_fix(transcript_id)
        # Ensure they are Segment models
        if fix and isinstance(fix[0], Segment):
            return fix
        # If fixtures returned dicts, coerce to Segment
        return [Segment(**s) if isinstance(s, dict) else s for s in fix]
    except Exception:
        return []

# ---- API ----
@router.get("/{transcript_id}", response_model=List[Segment], summary="List segments for a transcript (DB-first, fixtures-fallback)")
def get_segments(transcript_id: str, db: Session = Depends(get_db)):
    rows = _select_segments(db, transcript_id)
    if rows:
        return _as_segment_models(rows)

    # Fixtures fallback if DB has no rows for this transcript
    fix = _load_from_fixtures(transcript_id)
    if fix:
        return fix

    raise HTTPException(status_code=404, detail="No segments found for transcript")
