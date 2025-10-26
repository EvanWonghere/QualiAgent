from fastapi import APIRouter, HTTPException
from typing import List
from backend.contracts.models import EventWithLabels, Event, EventLabel, CodebookItem
from backend.repositories.fixtures_repo import load_codebook, load_segments
from backend.services.mock_scorer import MockScorer

router = APIRouter()
scorer = MockScorer()

@router.get("/queue", response_model=List[EventWithLabels])
def list_queue(transcript_id: str = "t.001"):
    segs = load_segments(transcript_id)
    evs = scorer.extract_events(segs)
    codebook = load_codebook()
    labels = scorer.label_events(evs, codebook)
    # Pair them up
    out = []
    for e in evs:
        out.append(EventWithLabels(event=e, labels=[l for l in labels if l.event_id == e.id]))
    return out

@router.post("/{label_id}/decision")
def review_decision(label_id: str):
    raise HTTPException(status_code=501, detail="Not implemented in Phase 0.5")
