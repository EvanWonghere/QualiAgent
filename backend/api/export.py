# backend/api/export.py
from fastapi import APIRouter, Response, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text as sql
from io import StringIO
import csv

from backend.db import SessionLocal
router = APIRouter()

def get_db():
    db = SessionLocal(); 
    try: yield db
    finally: db.close()

@router.get("/events.csv")
def export_events_csv(db: Session = Depends(get_db)):
    rows = db.execute(sql(
        "SELECT id,transcript_id,segment_id,summary,created_by,status,confidence,created_at,event_kind,raw_excerpt FROM events"
    )).mappings().all()
    buf = StringIO(); w = csv.DictWriter(buf, fieldnames=rows[0].keys() if rows else [])
    if rows: w.writeheader(); w.writerows(rows)
    return Response(content=buf.getvalue(), media_type="text/csv")

@router.get("/codebook.csv")
def export_codebook_csv(db: Session = Depends(get_db)):
    rows = db.execute(sql("SELECT id,name,display_name,definition,parent_id,status,created_at FROM codebook")).mappings().all()
    buf = StringIO(); w = csv.DictWriter(buf, fieldnames=rows[0].keys() if rows else [])
    if rows: w.writeheader(); w.writerows(rows)
    return Response(content=buf.getvalue(), media_type="text/csv")
