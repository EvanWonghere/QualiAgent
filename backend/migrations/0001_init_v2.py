# backend/migrations/0001_init_v2.py
"""
Initialize v2 domain tables for QualiAgent based on Pydantic contracts.
Ensures DB schema matches backend/contracts/models.py.

Creates (if missing):
  - segments
  - events
  - categories (New added)
  - codebook (Updated with category_id)
  - event_labels
  - label_reviews
"""
from __future__ import annotations
import sys
import os
from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Float, Text, DateTime,
    ForeignKey, JSON
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func
from sqlalchemy import inspect

# Ensure backend path is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# from backend.db import engine # Import engine for inspect (optional if passed in args)

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
    segments = Table(
        "segments", md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("index", Integer, nullable=False),
        Column("text", Text, nullable=False),
        Column("speaker", String, nullable=True),
        Column("start_char", Integer, nullable=True),
        Column("end_char", Integer, nullable=True),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- events ---
    events = Table(
        "events", md,
        Column("id", String, primary_key=True),
        Column("transcript_id", String, nullable=False, index=True),
        Column("segment_id", String, ForeignKey("segments.id", ondelete="SET NULL"), nullable=True, index=True),
        Column("start_char", Integer, nullable=True),
        Column("end_char", Integer, nullable=True),
        Column("summary", Text, nullable=False),
        Column("created_by", String, nullable=False),
        Column("status", String, nullable=False, default="proposed"),
        Column("confidence", Float, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- categories (New!) ---
    # Must be defined BEFORE codebook because codebook references it
    categories = Table(
        "categories", md,
        Column("id", Integer, primary_key=True),  # Auto-incrementing Integer ID
        Column("name", String, nullable=False, unique=True),
        Column("description", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        sqlite_autoincrement=True,
    )

    # --- codebook ---
    codebook = Table(
        "codebook", md,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False, unique=True),
        Column("display_name", String, nullable=True),
        Column("definition", Text, nullable=False),
        Column("parent_id", String, ForeignKey("codebook.id", name="fk_codebook_parent_id"), nullable=True),

        # [NEW] Add relationship to categories
        Column("category_id", Integer, ForeignKey("categories.id"), nullable=True),

        Column("status", String, nullable=False, default="active"),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- event_labels ---
    event_labels = Table(
        "event_labels", md,
        Column("id", String, primary_key=True),
        Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("codebook_id", String, ForeignKey("codebook.id", ondelete="RESTRICT"), nullable=False, index=True),
        Column("created_by", String, nullable=False),
        Column("rationale", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- label_reviews ---
    label_reviews = Table(
        "label_reviews", md,
        Column("id", String, primary_key=True),
        Column("event_label_id", String, ForeignKey("event_labels.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("reviewer", String, nullable=False),
        Column("decision", String, nullable=False),
        Column("notes", Text, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("source_meta", Text, nullable=True),
        sqlite_autoincrement=False,
    )

    # --- Create missing tables ---
    tables_to_create = []

    for table_obj in md.tables.values():
        if table_obj.name not in existing_table_names:
            tables_to_create.append(table_obj)

    if tables_to_create:
        print(f"Attempting to create tables: {[t.name for t in tables_to_create]}")
        try:
            # metadata.create_all handles creation order automatically based on FKs
            md.create_all(bind=engine_to_upgrade, tables=tables_to_create, checkfirst=True)

            # Verification
            inspector_after = inspect(engine_to_upgrade)
            current_tables = set(inspector_after.get_table_names())
            newly_created = current_tables - set(existing_table_names)
            print(f"Successfully created tables: {list(newly_created)}")

        except Exception as e:
            print(f"Error during table creation: {e}")
            raise
    else:
        print("All tables defined in migration 0001 already exist.")


def downgrade(engine: Engine) -> None:
    """Drops v2 domain tables."""
    print("Running downgrade for 0001...")
    md_to_drop = MetaData()

    # Reflect for dropping
    Table("label_reviews", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("event_labels", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("events", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("codebook", md_to_drop, autoload_with=engine, extend_existing=True)
    Table("categories", md_to_drop, autoload_with=engine, extend_existing=True)  # Don't forget to drop categories
    Table("segments", md_to_drop, autoload_with=engine, extend_existing=True)

    try:
        md_to_drop.drop_all(bind=engine, checkfirst=True)
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"Error during downgrade: {e}")