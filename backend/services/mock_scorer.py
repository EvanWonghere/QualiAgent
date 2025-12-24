import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from backend.contracts.models import Segment, Event, EventLabel, CodebookItem, SourceMeta
from .scorer_protocol import ScorerProtocol

FIX = Path(__file__).resolve().parents[1] / "fixtures"

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

class MockScorer(ScorerProtocol):
    def extract_events(self, segments: List[Segment]) -> List[Event]:
        now = datetime.now(timezone.utc).isoformat()
        # Deterministic: return 1 event per segment, copying a template from fixtures if present.
        events = []
        for seg in segments:
            events.append(Event(
                id=f"e.{seg.id}",
                transcript_id=seg.transcript_id,
                segment_id=seg.id,
                summary="研一上构建咨询师职业能力框架",
                created_by="AI",
                status="proposed",
                confidence=0.83,
                created_at=now,
                source_meta=SourceMeta(schema_version="2.0.0", engine_name="mock", engine_version="0.1")
            ))
        return events

    def label_events(self, events: List[Event], codebook: List[CodebookItem]) -> List[EventLabel]:
        now = datetime.now(timezone.utc).isoformat()
        labels = []
        # Always pick the first codebook item to keep it deterministic.
        cb0 = codebook[0]
        for ev in events:
            labels.append(EventLabel(
                id=f"l.{ev.id}",
                event_id=ev.id,
                codebook_id=cb0.id,
                created_by="AI",
                created_at=now
            ))
        return labels
