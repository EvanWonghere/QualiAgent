# backend/api/review.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from pydantic import BaseModel

from backend.db import SessionLocal
from backend.models import Event, EventLabel, Segment, Codebook

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Models ---
class LabelOut(BaseModel):
    code_name: str
    rationale: Optional[str] = None


class ReviewItem(BaseModel):
    event_id: str
    segment_text: str
    summary: str
    confidence: float
    status: str
    # ✨✨✨ 修复核心：把 code_name 提出来，方便前端直接读取 ✨✨✨
    code_name: Optional[str] = None
    labels: List[LabelOut]

    class Config:
        from_attributes = True


class ReviewAction(BaseModel):
    action: str  # "accept", "reject"


class BulkReviewAction(BaseModel):
    action: str  # "accept_all", "reject_all"


# --- Endpoints ---

@router.get("/queue", response_model=List[ReviewItem])
def get_review_queue(db: Session = Depends(get_db)):
    """
    获取审核队列
    """
    events = db.query(Event) \
        .options(
        joinedload(Event.segment),
        joinedload(Event.labels)
    ) \
        .filter(Event.status == "proposed") \
        .order_by(desc(Event.confidence)) \
        .all()

    results = []
    for e in events:
        seg_text = e.segment.text if e.segment else "(Segment missing)"

        # ✨✨✨ 提取第一个标签的名字 ✨✨✨
        first_code = "No Label"
        if e.labels and len(e.labels) > 0:
            first_code = e.labels[0].code_name

        results.append({
            "event_id": e.id,
            "segment_text": seg_text,
            "summary": e.summary,
            "confidence": e.confidence or 0.8,
            "status": e.status,
            "code_name": first_code,  # 👈 这里赋值！前端就能拿到了
            "labels": [{"code_name": l.code_name, "rationale": l.rationale} for l in e.labels]
        })

    return results


@router.post("/queue/batch")
def batch_process_review(payload: BulkReviewAction, db: Session = Depends(get_db)):
    """
    一键接受或拒绝
    """
    pending_events = db.query(Event).filter(Event.status == 'proposed').all()

    if not pending_events:
        return {"status": "no_events", "count": 0}

    count = 0
    if payload.action == "accept_all":
        for evt in pending_events:
            evt.status = "accepted"
            for label in evt.labels:
                cb = db.query(Codebook).filter(Codebook.id == label.codebook_id).first()
                if cb and cb.status == 'proposed':
                    cb.status = 'active'
            count += 1

    elif payload.action == "reject_all":
        for evt in pending_events:
            evt.status = "rejected"
            count += 1

    db.commit()
    return {"status": "ok", "action": payload.action, "count": count}


@router.post("/{event_id}")
def process_single_event(event_id: str, payload: ReviewAction, db: Session = Depends(get_db)):
    """
    处理单个 Accept / Reject
    """
    evt = db.query(Event).filter(Event.id == event_id).first()
    if not evt: raise HTTPException(404, "Event not found")

    if payload.action == "accept":
        evt.status = "accepted"
        for label in evt.labels:
            cb = db.query(Codebook).filter(Codebook.id == label.codebook_id).first()
            if cb and cb.status == 'proposed':
                cb.status = 'active'

    elif payload.action == "reject":
        evt.status = "rejected"

    db.commit()
    return {"status": "ok", "action": payload.action}