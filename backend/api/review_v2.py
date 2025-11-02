# backend/api/review_v2.py
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend.repositories import sql_repo as repo

router = APIRouter()

def get_db():
    db = SessionLocal(); 
    try: yield db
    finally: db.close()

class DecisionIn(BaseModel):
    reviewer: str
    notes: Optional[str] = None

class EventEditIn(BaseModel):
    reviewer: str
    summary: Optional[str] = None
    status: Optional[str] = None   # e.g., 'accepted'
    notes: Optional[str] = None

class AddLabelIn(BaseModel):
    reviewer: str
    codebook_id: str
    rationale: Optional[str] = None

@router.get("/queue", tags=["review"], summary="DB-backed review queue")
def list_queue(transcript_id: Optional[str] = None, db: Session = Depends(get_db)):
    return repo.list_review_queue(db, transcript_id)

@router.post("/event/{event_id}/accept", tags=["review"])
def accept_event(event_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    e = repo.get_event(db, event_id)
    if not e: raise HTTPException(404, "event not found")
    repo.update_event_status(db, event_id, "accepted")
    return {"ok": True}

@router.post("/event/{event_id}/reject", tags=["review"])
def reject_event(event_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    e = repo.get_event(db, event_id)
    if not e: raise HTTPException(404, "event not found")
    repo.update_event_status(db, event_id, "rejected")
    return {"ok": True}

@router.post("/event/{event_id}/edit", tags=["review"])
def edit_event(event_id: str, body: EventEditIn, db: Session = Depends(get_db)):
    e = repo.get_event(db, event_id)
    if not e: raise HTTPException(404, "event not found")
    updates = {}
    if body.summary: updates["summary"] = body.summary
    if body.status: updates["status"] = body.status
    repo.patch_event(db, event_id, updates)
    return {"ok": True}

@router.post("/label/{label_id}/accept", tags=["review"])
def accept_label(label_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    repo.insert_label_review(db, label_id, body.reviewer, "accept", body.notes)
    return {"ok": True}

@router.post("/label/{label_id}/reject", tags=["review"])
def reject_label(label_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    repo.insert_label_review(db, label_id, body.reviewer, "reject", body.notes)
    return {"ok": True}

@router.post("/event/{event_id}/add_label", tags=["review"])
def add_label(event_id: str, body: AddLabelIn, db: Session = Depends(get_db)):
    repo.add_event_label(db, event_id, body.codebook_id, "human", body.rationale)
    return {"ok": True}
