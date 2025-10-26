# backend/migrations/0001_init_v2.py
"""
Initialize v2 domain tables for QualiAgent (idempotent, SQLite-safe).

Creates:
  - segments
  - events
  - codebook
  - event_labels
  - label_reviews
"""

from __future__ import annotations
from sqlalchemy import (
    MetaData, Table, Column, String, Float, Text, DateTime,
    ForeignKey
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func


def upgrade(engine: Engine) -> None:
    """
    Create v2 domain tables. Safe to call multiple times.
    """
    md = MetaData()

    # --- segments ---
    # Unit of analysis for events; typically per utterance/turn.
    segments = Table(
        "segments",
        md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("speaker", String, nullable=True),
        Column("start_offset", Float, nullable=True),  # seconds
        Column("end_offset", Float, nullable=True),    # seconds
        Column("text", Text, nullable=False),
        Column("meta", JSON, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- events ---
    # Spans within a segment capturing a specific coding target.
    events = Table(
        "events",
        md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("segment_id", String, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("start_offset", Float, nullable=True),  # within segment
        Column("end_offset", Float, nullable=True),    # within segment
        Column("kind", String, nullable=True),         # optional coarse type
        Column("confidence", Float, nullable=True),
        Column("payload", JSON, nullable=True),        # model-specific payload
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sqlite_autoincrement=False,
    )

    # --- codebook ---
    codebook = Table(
        "codebook",
        md,
        Column("code", String, primary_key=True),    # stable code id, e.g. "E1"
        Column("label", String, nullable=False),     # human label
        Column("definition", Text, nullable=True),
        Column("tags", JSON, nullable=True),         # list[str]
        Column("examples", JSON, nullable=True),     # list[str]
    )

    # --- event_labels ---
    # Human/model assignments of codes to events.
    event_labels = Table(
        "event_labels",
        md,
        Column("id", String, primary_key=True),
        Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("code", String, ForeignKey("codebook.code", ondelete="RESTRICT"), nullable=False, index=True),
        Column("labeler", String, nullable=True),         # "model:mock", "rater:alice"
        Column("score", Float, nullable=True),            # confidence / rating
        Column("rationale", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sqlite_autoincrement=False,
    )

    # --- label_reviews ---
    # Meta-review of labels (QA/consensus step).
    label_reviews = Table(
        "label_reviews",
        md,
        Column("id", String, primary_key=True),
        Column("event_label_id", String, ForeignKey("event_labels.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("reviewer", String, nullable=True),
        Column("status", String, nullable=False, default="pending"),  # "approved" | "rejected" | "changes_requested" | "pending"
        Column("comment", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        sqlite_autoincrement=False,
    )

    # Create any missing tables and indexes; if they already exist, no-op.
    md.create_all(bind=engine)


def downgrade(engine: Engine) -> None:
    """
    Drop v2 domain tables (reverse of upgrade).
    """
    md = MetaData()
    md.reflect(bind=engine)

    # Drop in FK-safe order
    for name in ("label_reviews", "event_labels", "events", "codebook", "segments"):
        if name in md.tables:
            md.tables[name].drop(bind=engine, checkfirst=True)
