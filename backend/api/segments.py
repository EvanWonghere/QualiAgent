# backend/api/segments.py
from fastapi import APIRouter, HTTPException
from typing import List
from backend.contracts.models import Segment
from backend.repositories.fixtures_repo import load_segments

router = APIRouter()

@router.get("/{transcript_id}", response_model=List[Segment])
def get_segments(transcript_id: str):
    segs = load_segments(transcript_id)
    if not segs:
        raise HTTPException(status_code=404, detail="No segments found for transcript")
    return segs
