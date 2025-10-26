# backend/contracts/models.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# Shared types
CreatedBy = Literal["AI", "human"]
EventStatus = Literal["proposed", "accepted", "rejected", "edited"]
ReviewDecisionType = Literal["accept", "revise", "reject"]
CodeStatus = Literal["active", "deprecated"]

class SourceMeta(BaseModel):
    schema_version: str = "2.0.0"
    source_system: Optional[str] = None       # e.g., "nvivo", "atlas-ti", "csv"
    import_id: Optional[str] = None           # trace batch import
    prompt_hash: Optional[str] = None         # for AI-generated content
    engine_name: Optional[str] = None
    engine_version: Optional[str] = None

class Segment(BaseModel):
    id: str
    transcript_id: str
    index: int
    text: str
    speaker: Optional[str] = None
    start_char: Optional[int] = Field(default=None, ge=0)
    end_char: Optional[int] = Field(default=None, ge=0)
    source_meta: Optional[SourceMeta] = None

class Event(BaseModel):
    id: str
    transcript_id: str
    segment_id: Optional[str] = None
    start_char: Optional[int] = Field(default=None, ge=0)
    end_char: Optional[int] = Field(default=None, ge=0)
    summary: str
    created_by: CreatedBy
    status: EventStatus = "proposed"
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    created_at: datetime
    source_meta: Optional[SourceMeta] = None

class CodebookItem(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    definition: str
    parent_id: Optional[str] = None
    status: CodeStatus = "active"
    created_at: datetime
    source_meta: Optional[SourceMeta] = None

class EventLabel(BaseModel):
    id: str
    event_id: str
    codebook_id: str
    created_by: CreatedBy
    rationale: Optional[str] = None
    created_at: datetime
    source_meta: Optional[SourceMeta] = None

class ReviewDecision(BaseModel):
    id: str
    event_label_id: str
    reviewer: str
    decision: ReviewDecisionType
    notes: Optional[str] = None
    created_at: datetime
    source_meta: Optional[SourceMeta] = None

# Convenience compound responses
class EventWithLabels(BaseModel):
    event: Event
    labels: List[EventLabel] = []

class CodebookTreeNode(BaseModel):
    item: CodebookItem
    children: List["CodebookTreeNode"] = []
