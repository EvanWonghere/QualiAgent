# backend/api/transcripts.py
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, defer
from sqlalchemy import desc
from pydantic import BaseModel, Field

from backend.db import SessionLocal
from backend.models import Transcript

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Schemas ---
class TranscriptBase(BaseModel):
    id: str
    filename: Optional[str] = Field(None, alias="title")
    created_at: Optional[datetime] = None
    # ✨ 新增：让前端能看到状态
    status: Optional[str] = "ready"

    class Config:
        from_attributes = True
        populate_by_name = True


class TranscriptListOut(TranscriptBase):
    pass


class TranscriptDetailOut(TranscriptBase):
    content: Optional[str] = None


# --- Endpoints ---

@router.get("/", response_model=List[TranscriptListOut])
def get_all_transcripts(db: Session = Depends(get_db)):
    """获取列表"""
    return db.query(Transcript) \
        .options(defer(Transcript.content)) \
        .order_by(desc(Transcript.created_at)) \
        .all()


@router.get("/{tid}", response_model=TranscriptDetailOut)
def get_transcript_detail(tid: str, db: Session = Depends(get_db)):
    """获取详情"""
    t = db.query(Transcript).filter(Transcript.id == tid).first()
    if not t:
        raise HTTPException(404, "Transcript not found")
    return t


@router.delete("/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcript(tid: str, db: Session = Depends(get_db)):
    """删除"""
    t = db.query(Transcript).filter(Transcript.id == tid).first()
    if not t:
        raise HTTPException(404, "Transcript not found")
    db.delete(t)
    db.commit()
    return None