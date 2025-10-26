from pathlib import Path
import json
from typing import List
from backend.contracts.models import Segment, Event, EventLabel, CodebookItem

FIX = Path(__file__).resolve().parents[1] / "fixtures"

def load_codebook() -> List[CodebookItem]:
    data = json.loads((FIX / "codebook.json").read_text(encoding="utf-8"))
    return [CodebookItem(**d) for d in data]

def load_segments(transcript_id: str) -> List[Segment]:
    segs = []
    for line in (FIX / "segments.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d["transcript_id"] == transcript_id:
            segs.append(Segment(**d))
    return segs
