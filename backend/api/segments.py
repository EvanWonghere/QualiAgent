# backend/api/segments.py
from __future__ import annotations
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text as sql
from sqlalchemy.orm import Session

from backend.db import SessionLocal
# ✅ 引用官方合约模型，不再自己造轮子
from backend.contracts.models import Segment

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _select_segments(db: Session, transcript_id: str) -> List[Dict[str, Any]]:
    """
    查询数据库，并把字段名从 DB 格式翻译成 API 格式
    """
    try:
        # ✅ 核心修复：
        # 1. 查 sentence_index 改名为 index
        # 2. 查 start_offset 改名为 start_char
        # 3. 查 speaker (现在数据库里有这个字段了)
        q = """
        SELECT
            id,
            transcript_id,
            sentence_index AS "index",
            text,
            speaker,
            start_offset AS "start_char",
            end_offset AS "end_char"
        FROM segments
        WHERE transcript_id = :tid
        ORDER BY sentence_index ASC
        """
        rows = [dict(r) for r in db.execute(sql(q), {"tid": transcript_id}).mappings().all()]
        return rows
    except Exception as e:
        print(f"Error querying segments: {e}")
        return []


def _as_segment_models(rows: List[Dict[str, Any]]) -> List[Segment]:
    out: List[Segment] = []
    for idx, r in enumerate(rows):
        final_index = r.get("index")
        if final_index is None:
            final_index = idx + 1

        # ✅ 构造符合 contracts.models.Segment 的数据
        data = {
            "id": str(r.get("id")),
            "transcript_id": str(r.get("transcript_id")),
            "index": final_index,
            "text": r.get("text") or "",
            "speaker": r.get("speaker"),
            "start_char": r.get("start_char"),
            "end_char": r.get("end_char"),
            "source_meta": None
        }
        out.append(Segment(**data))
    return out


# 保留 Fixtures 回退功能
def _load_from_fixtures(transcript_id: str) -> List[Segment]:
    try:
        from backend.repositories.fixtures_repo import load_segments as load_fix
        fix = load_fix(transcript_id)
        out = []
        for item in fix:
            if isinstance(item, dict):
                out.append(Segment(**item))
            elif hasattr(item, '__dict__'):
                out.append(Segment(**item.__dict__))
            else:
                out.append(item)
        return out
    except Exception:
        return []


@router.get("/{transcript_id}", response_model=List[Segment])
def get_segments(transcript_id: str, db: Session = Depends(get_db)):
    rows = _select_segments(db, transcript_id)
    if rows:
        return _as_segment_models(rows)

    fix = _load_from_fixtures(transcript_id)
    if fix:
        return fix

    return []