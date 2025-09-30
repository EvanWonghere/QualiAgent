# backend/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime

# ✨ Import Base from the new db.py file
from .db import Base


class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, nullable=False)
    file_path = Column(String, nullable=False)
    # ✨ NEW: Status to track AI processing state.
    status = Column(String, default="new", nullable=False) # States: "new", "processing", "processed", "failed"

    chunks = relationship("Chunk", back_populates="transcript", cascade="all, delete")
    codes = relationship("Code", back_populates="transcript")


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(Integer, primary_key=True, index=True)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"))
    text = Column(Text)
    embedding = Column(Text)
    start_pos = Column(Integer)
    end_pos = Column(Integer)
    transcript = relationship("Transcript", back_populates="chunks")


class Memo(Base):
    __tablename__ = "memos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    codes = relationship("Code", back_populates="memo")


class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, index=True)
    excerpt = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=True)
    memo_id = Column(Integer, ForeignKey("memos.id"), nullable=True)
    transcript = relationship("Transcript", back_populates="codes")
    memo = relationship("Memo", back_populates="codes")

# 🧹 CLEANUP: The init_db function is no longer needed here as it's handled by main.py