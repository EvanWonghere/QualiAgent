from __future__ import annotations
from typing import Protocol, List
from backend.contracts.models import Segment, Event, EventLabel, CodebookItem

class ScorerProtocol(Protocol):
    def extract_events(self, segments: List[Segment]) -> List[Event]: ...
    def label_events(self, events: List[Event], codebook: List[CodebookItem]) -> List[EventLabel]: ...
