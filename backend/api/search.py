# backend/api/search.py
from __future__ import annotations
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sql
from sqlalchemy.orm import Session
from backend.db import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SegmentHit(BaseModel):
    id: str
    transcript_id: str
    index: int
    speaker: Optional[str] = None
    text: str
    score: float

# --- Config ---
USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "1").strip().lower() not in ("0", "false", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE_URL")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
USE_OPENAI = bool(OPENAI_KEY) and USE_EMBEDDINGS

# Optional OpenAI client
oai = None
if USE_OPENAI:
    try:
        from openai import OpenAI
        if OPENAI_BASE_URL:
            oai = OpenAI(api_key=OPENAI_KEY, base_url=OPENAI_BASE_URL)
        else:
            oai = OpenAI(api_key=OPENAI_KEY)
    except Exception:
        oai = None
        USE_OPENAI = False  # force fallback

def _fetch_segments(db: Session, transcript_id: Optional[str], limit_rows: int = 5000):
    if transcript_id:
        rows = db.execute(sql(
            "SELECT id, transcript_id, [index], speaker, text "
            "FROM segments WHERE transcript_id=:tid ORDER BY [index] ASC LIMIT :lim"
        ), {"tid": transcript_id, "lim": limit_rows}).mappings().all()
    else:
        rows = db.execute(sql(
            "SELECT id, transcript_id, [index], speaker, text FROM segments LIMIT :lim"
        ), {"lim": limit_rows}).mappings().all()
    return rows

def _embed_texts(texts: List[str]) -> List[List[float]]:
    if not (USE_OPENAI and oai):
        return []
    resp = oai.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def _char_ngrams(s: str, n: int = 2) -> set:
    # whitespace-insensitive character n-grams (good enough for CJK fallback)
    s = "".join(str(s).split())
    if not s:
        return set()
    if len(s) < n:
        return {s}
    return {s[i:i+n] for i in range(len(s)-n+1)}

@router.get("/v2", response_model=List[SegmentHit])
def search_v2(q: str = Query(..., min_length=1),
              transcript_id: Optional[str] = None,
              limit: int = 10,
              db: Session = Depends(get_db)):
    rows = _fetch_segments(db, transcript_id)
    if not rows:
        raise HTTPException(404, "No segments available")

    # Embedding mode (if configured)
    if USE_OPENAI and oai:
        try:
            qv = _embed_texts([q])[0]
            seg_texts = [r["text"] for r in rows]
            seg_vecs = _embed_texts(seg_texts)
            scored = []
            # cosine
            import math
            def cos(a, b):
                dot = sum(x*y for x, y in zip(a, b))
                na = math.sqrt(sum(x*x for x in a)) or 1e-9
                nb = math.sqrt(sum(x*x for x in b)) or 1e-9
                return dot / (na * nb)
            for r, v in zip(rows, seg_vecs):
                scored.append((r, cos(qv, v)))
            scored.sort(key=lambda t: t[1], reverse=True)
            return [SegmentHit(
                id=str(s[0]["id"]), transcript_id=str(s[0]["transcript_id"]),
                index=int(s[0]["index"]), speaker=s[0]["speaker"], text=s[0]["text"],
                score=float(s[1])
            ) for s in scored[:limit]]
        except Exception:
            # fall through to CJK-aware fallback
            pass

    # CJK-aware fallback: character bigram Jaccard
    qg = _char_ngrams(q, 2)
    scored = []
    for r in rows:
        rg = _char_ngrams(r["text"], 2)
        inter = len(qg & rg)
        union = len(qg | rg) or 1
        score = inter / union
        scored.append((r, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return [SegmentHit(
        id=str(s[0]["id"]), transcript_id=str(s[0]["transcript_id"]),
        index=int(s[0]["index"]), speaker=s[0]["speaker"], text=s[0]["text"],
        score=float(s[1])
    ) for s in scored[:limit]]
