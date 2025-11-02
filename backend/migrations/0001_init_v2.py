# backend/migrations/0001_init_v2.py
"""
Initialize v2 domain tables for QualiAgent based on Pydantic contracts.
Ensures DB schema matches backend/contracts/models.py.

Creates (if missing):
  - segments
  - events
  - codebook
  - event_labels
  - label_reviews
"""
from __future__ import annotations
import sys
import os
from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Float, Text, DateTime,
    ForeignKey, JSON # Keep JSON if needed for source_meta, though Pydantic handles serialization
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func
from sqlalchemy import inspect # Used to check for existing tables

# Ensure backend path is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import engine # Import engine for inspect

def upgrade(engine_to_upgrade: Engine) -> None:
    """
    Create v2 domain tables aligned with backend/contracts/models.py.
    Safe to call multiple times (idempotent).
    """
    print("Running migration 0001: Initialize V2 tables based on Pydantic contracts...")
    md = MetaData()
    inspector = inspect(engine_to_upgrade)
    existing_table_names = inspector.get_table_names()
    print(f"Existing tables found: {existing_table_names}")

    # --- segments ---
    # Matches contracts.models.Segment
    segments = Table(
        "segments", md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("index", Integer, nullable=False), # Assuming index is required
        Column("text", Text, nullable=False),
        Column("speaker", String, nullable=True),
        Column("start_char", Integer, nullable=True),
        Column("end_char", Integer, nullable=True),
        # Assuming source_meta is stored as JSON text in SQLite
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- events ---
    # Matches contracts.models.Event
    events = Table(
        "events", md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("segment_id", String, ForeignKey("segments.id", ondelete="SET NULL"), nullable=True, index=True), # Allow NULL, SET NULL on delete
        Column("start_char", Integer, nullable=True),
        Column("end_char", Integer, nullable=True),
        Column("summary", Text, nullable=False), # Changed from Nullable based on Pydantic
        Column("created_by", String, nullable=False), # Maps to Literal["AI", "human"]
        Column("status", String, nullable=False, default="proposed"), # Maps to EventStatus Literal
        Column("confidence", Float, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False), # Removed server_default for broader DB compat
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- codebook ---
    # Matches contracts.models.CodebookItem
    codebook = Table(
        "codebook", md,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False, unique=True), # Added unique constraint likely needed
        Column("display_name", String, nullable=True),
        Column("definition", Text, nullable=False), # Changed from Nullable based on Pydantic
        # Self-referential FK needs careful handling or deferred constraint in some DBs
        Column("parent_id", String, ForeignKey("codebook.id", name="fk_codebook_parent_id"), nullable=True),
        Column("status", String, nullable=False, default="active"), # Maps to CodeStatus Literal
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- event_labels ---
    # Matches contracts.models.EventLabel
    event_labels = Table(
        "event_labels", md,
        Column("id", String, primary_key=True),
        Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("codebook_id", String, ForeignKey("codebook.id", ondelete="RESTRICT"), nullable=False, index=True),
        Column("created_by", String, nullable=False), # Maps to CreatedBy Literal
        Column("rationale", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- label_reviews ---
    # Matches contracts.models.ReviewDecision
    label_reviews = Table(
        "label_reviews", md,
        Column("id", String, primary_key=True),
        Column("event_label_id", String, ForeignKey("event_labels.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("reviewer", String, nullable=False), # Changed from Nullable based on Pydantic
        Column("decision", String, nullable=False), # Maps to ReviewDecisionType Literal
        Column("notes", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- Create missing tables ---
    tables_to_create = []
    created_table_names = set()

    for table_obj in md.tables.values():
        if table_obj.name not in existing_table_names:
            tables_to_create.append(table_obj)

    if tables_to_create:
        print(f"Attempting to create tables: {[t.name for t in tables_to_create]}")
        try:
            # Use metadata.create_all to handle table creation idempotently
            md.create_all(bind=engine_to_upgrade, tables=tables_to_create, checkfirst=True)

            # Verify which tables were actually created
            inspector_after = inspect(engine_to_upgrade)
            current_tables = set(inspector_after.get_table_names())
            newly_created = current_tables - set(existing_table_names)
            if newly_created:
                print(f"Successfully created tables: {list(newly_created)}")
            else:
                 print("No new tables were created (likely already existed).")

        except Exception as e:
            print(f"Error during table creation: {e}")
            raise
    else:
        print("All tables defined in migration 0001 already exist.")


def downgrade(engine: Engine) -> None:
    """Drops v2 domain tables based on Pydantic contract structure."""
    print("Running downgrade for 0001 (based on Pydantic contracts)...")
    # Define metadata based on Pydantic models for dropping
    md_to_drop = MetaData()
    # Re-declare tables exactly as in upgrade to ensure correct drop order resolution
    # (Or rely on reflection if confident) - using declaration is safer
    Table("label_reviews", md_to_drop, autoload_with=engine, extend_existing=True) # Reflect existing structure
    Table("event_labels", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("events", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("codebook", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("segments", md_to_drop, autoload_with=engine, extend_existing=True)

    try:
        # Drop tables in reverse order of creation (metadata handles FK constraints)
        md_to_drop.drop_all(bind=engine, checkfirst=True)
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"Error during downgrade: {e}")