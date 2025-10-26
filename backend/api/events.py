# backend/api/events.py
from typing import List
from fastapi import APIRouter, HTTPException

from backend.contracts.models import Segment, Event, EventLabel, CodebookItem
from backend.repositories.fixtures_repo import load_codebook, load_segments
from backend.services.mock_scorer import MockScorer

router = APIRouter()
scorer = MockScorer()


# ----- Core helpers so GET/POST can share logic -----
def _propose_events_core(transcript_id: str) -> List[Event]:
    segs: List[Segment] = load_segments(transcript_id)
    if not segs:
        raise HTTPException(status_code=404, detail=f"No segments found for transcript '{transcript_id}'")
    return scorer.extract_events(segs)


def _label_events_core(transcript_id: str) -> List[EventLabel]:
    segs: List[Segment] = load_segments(transcript_id)
    if not segs:
        raise HTTPException(status_code=404, detail=f"No segments found for transcript '{transcript_id}'")
    events = scorer.extract_events(segs)
    codebook: List[CodebookItem] = load_codebook()
    return scorer.label_events(events, codebook)


# ----- Propose events -----
@router.post("/propose/{transcript_id}", response_model=List[Event])
def propose_events_post(transcript_id: str):
    return _propose_events_core(transcript_id)


# Convenience GET for browser/curl testing
@router.get("/propose/{transcript_id}", response_model=List[Event])
def propose_events_get(transcript_id: str):
    return _propose_events_core(transcript_id)


# ----- Label events -----
@router.post("/label/{transcript_id}", response_model=List[EventLabel])
def label_events_post(transcript_id: str):
    return _label_events_core(transcript_id)


# Convenience GET for browser/curl testing
@router.get("/label/{transcript_id}", response_model=List[EventLabel])
def label_events_get(transcript_id: str):
    return _label_events_core(transcript_id)
