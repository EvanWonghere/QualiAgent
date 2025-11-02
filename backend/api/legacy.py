# backend/api/legacy.py
from __future__ import annotations
from typing import Any, Dict, Optional, List, Union
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text as sql

from backend.db import SessionLocal
from backend import services  # your V1 services (if present)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- Models ----
class MemoPreviewIn(BaseModel):
    text: str
    title: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

class MemoPreviewOut(BaseModel):
    title: str
    content: str
    source: str = "legacy"

class GenerateCodesIn(BaseModel):
    text: Optional[str] = None
    transcript_id: Optional[Union[str, int]] = None
    top_k: Optional[int] = 10

class CodeOut(BaseModel):
    code: str
    excerpt: str
    transcript_id: Optional[str] = None
    source: str = "legacy"

class SearchOut(BaseModel):
    id: str
    transcript_id: Optional[str] = None
    text: str
    score: float

def _hasattr(obj, name: str) -> bool:
    try:
        getattr(obj, name)
        return True
    except Exception:
        return False

def _char_ngrams(s: str, n: int = 2) -> set:
    s = "".join(str(s).split())
    if not s:
        return set()
    if len(s) < n:
        return {s}
    return {s[i:i+n] for i in range(len(s)-n+1)}

# ---- Endpoints ----
@router.post("/memo_preview", response_model=MemoPreviewOut)
def memo_preview(payload: MemoPreviewIn, db: Session = Depends(get_db)):
    for fname in ["generate_memo_preview", "generate_ai_memo_preview", "memo_preview"]:
        if _hasattr(services, fname):
            fn = getattr(services, fname)
            try:
                result = fn(db=db, text=payload.text, params=payload.params)
                if isinstance(result, dict) and "title" in result and "content" in result:
                    return MemoPreviewOut(**result, source="legacy")
            except TypeError:
                result = fn(payload.text)
                if isinstance(result, dict) and "title" in result and "content" in result:
                    return MemoPreviewOut(**result, source="legacy")
            except Exception as e:
                raise HTTPException(500, f"Legacy memo_preview failed: {e}")
    # Fallback
    title = payload.title or "Memo Preview"
    content = (payload.text[:1200] + "…") if len(payload.text) > 1200 else payload.text
    return MemoPreviewOut(title=title, content=content, source="legacy")

@router.post("/generate_codes", response_model=List[CodeOut])
def generate_codes(payload: GenerateCodesIn, db: Session = Depends(get_db)):
    # Prefer a V1 generator if present
    for fname in ["generate_ai_codes", "generate_codes", "generate_codes_for_transcript"]:
        if _hasattr(services, fname):
            fn = getattr(services, fname)
            try:
                result = fn(db=db, transcript_id=payload.transcript_id, text=payload.text, top_k=payload.top_k)
                if isinstance(result, list) and result and isinstance(result[0], dict):
                    out: List[CodeOut] = []
                    for r in result:
                        out.append(CodeOut(
                            code=r.get("code") or r.get("label") or "",
                            excerpt=r.get("excerpt") or r.get("text") or "",
                            transcript_id=str(r.get("transcript_id")) if r.get("transcript_id") is not None else None,
                            source="legacy"
                        ))
                    return out
            except TypeError:
                pass
            except Exception as e:
                raise HTTPException(500, f"Legacy generate_codes failed: {e}")

    # Fallback: if transcript_id provided, fetch text from segments
    text_source = payload.text
    if not text_source and payload.transcript_id is not None:
        rows = db.execute(sql(
            "SELECT text FROM segments WHERE transcript_id=:tid ORDER BY [index] ASC"
        ), {"tid": str(payload.transcript_id)}).mappings().all()
        text_source = "\n".join([r["text"] for r in rows]) if rows else ""

    # Regex parse for (Label: Summary) in Chinese/English punctuation
    if not text_source:
        raise HTTPException(501, "No legacy generator found and no text available to parse.")

    import re
    patterns = [
        re.compile(r"\((?P<label>[^():（）]{1,40})\s*[:：]\s*(?P<summary>[^()（）]{1,200})\)"),
        re.compile(r"（(?P<label>[^():（）]{1,40})\s*[:：]\s*(?P<summary>[^()（）]{1,200})）"),
    ]
    out: List[CodeOut] = []
    for pat in patterns:
        for m in pat.finditer(text_source):
            out.append(CodeOut(
                code=m.group("label").strip(),
                excerpt=m.group("summary").strip(),
                transcript_id=str(payload.transcript_id) if payload.transcript_id is not None else None,
                source="legacy"
            ))
    if not out:
        raise HTTPException(404, "No (Label: Summary) pairs found in the provided text/transcript.")
    return out

@router.get("/search", response_model=List[SearchOut])
def legacy_search(q: str = Query(..., min_length=1), limit: int = 10, db: Session = Depends(get_db)):
    # Try V1 semantic search if present
    for fname in ["semantic_search", "semantic_search_chunks", "search_chunks"]:
        if _hasattr(services, fname):
            fn = getattr(services, fname)
            try:
                result = fn(db=db, query=q, limit=limit)
                out: List[SearchOut] = []
                if isinstance(result, list):
                    for r in result:
                        if isinstance(r, dict):
                            out.append(SearchOut(
                                id=str(r.get("id", "")),
                                transcript_id=str(r.get("transcript_id")) if r.get("transcript_id") is not None else None,
                                text=r.get("text") or r.get("content") or r.get("excerpt") or "",
                                score=float(r.get("score") or r.get("similarity") or 0.0),
                            ))
                return out
            except Exception as e:
                raise HTTPException(500, f"Legacy semantic_search failed: {e}")

    # Fallback: rank by CJK n-gram overlap over chunks if present, else segments
    # rows = db.execute(sql("SELECT id, transcript_id, content as text FROM chunks LIMIT :lim"), {"lim": 5000}).mappings().all()
    # if not rows:
    rows = db.execute(sql("SELECT id, transcript_id, text FROM segments LIMIT :lim"), {"lim": 5000}).mappings().all()

    qg = _char_ngrams(q, 2)
    scored = []
    for r in rows:
        rg = _char_ngrams(r["text"], 2)
        inter = len(qg & rg)
        union = len(qg | rg) or 1
        score = inter / union
        scored.append({"id": str(r["id"]), "transcript_id": str(r["transcript_id"]), "text": r["text"], "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [SearchOut(**x) for x in scored[:limit]]
