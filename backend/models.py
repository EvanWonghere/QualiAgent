# backend/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


# --- 1. 访谈文稿 ---
class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, default="ready")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    segments = relationship("Segment", back_populates="transcript", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="transcript", cascade="all, delete-orphan")


# --- 2. 文本切片 ---
class Segment(Base):
    __tablename__ = "segments"
    id = Column(String, primary_key=True)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    sentence_index = Column(Integer)
    text = Column(Text)
    start_offset = Column(Integer)
    end_offset = Column(Integer)
    speaker = Column(String, nullable=True)
    transcript = relationship("Transcript", back_populates="segments")
    events = relationship("Event", back_populates="segment")


# --- ✨ 新增：编码库 (CodebookLibrary) ---
class CodebookLibrary(Base):
    __tablename__ = "codebook_libraries"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)  # 例如 "项目A", "情感分析专用"
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联具体的 codes
    codes = relationship("Codebook", back_populates="library", cascade="all, delete-orphan")


# --- 3. 编码 (Codebook) ---
class Codebook(Base):
    __tablename__ = "codebook"
    id = Column(String, primary_key=True)

    # ✨ 新增：关联到 Library
    library_id = Column(String, ForeignKey("codebook_libraries.id"), nullable=True)

    code = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    library = relationship("CodebookLibrary", back_populates="codes")


# --- 4. 分析事件 (Event) ---
class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    transcript_id = Column(String, ForeignKey("transcripts.id"))
    segment_id = Column(String, ForeignKey("segments.id"))
    summary = Column(Text)
    status = Column(String, default="proposed")
    confidence = Column(Float, default=0.0)
    created_by = Column(String, default="AI")
    transcript = relationship("Transcript", back_populates="events")
    segment = relationship("Segment", back_populates="events")
    labels = relationship("EventLabel", back_populates="event", cascade="all, delete-orphan")


# --- 5. 关联表 (EventLabel) ---
class EventLabel(Base):
    __tablename__ = "event_labels"
    event_id = Column(String, ForeignKey("events.id"), primary_key=True)
    codebook_id = Column(String, ForeignKey("codebook.id"), primary_key=True)
    code_name = Column(String)
    created_by = Column(String, default="AI")
    rationale = Column(Text)
    event = relationship("Event", back_populates="labels")