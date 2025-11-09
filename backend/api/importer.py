# backend/api/importer.py
from __future__ import annotations
import os, uuid, shutil, json
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from sqlalchemy import text as sql
from backend.db import engine
from backend.importers.docx_importer import parse_docx

router = APIRouter()

# backend/api/importer.py

# --- helpers -------------------------------------------------------------

def _table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(sql(f"PRAGMA table_info('{table}')")).fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}

def _map_segment_row_to_schema(row: Dict[str, Any], present_cols: set[str]) -> Dict[str, Any]:
    """
    Adapt incoming segment dict to match the live DB schema.
    Handles reserved names and alternate column naming.
    """
    r = dict(row)  # shallow copy

    # source_meta -> meta (if DB uses 'meta')
    if "source_meta" in r and "meta" in present_cols and "source_meta" not in present_cols:
        r["meta"] = r.pop("source_meta")

    # index -> sentence_index (if DB uses sentence_index)
    if "index" in r and "sentence_index" in present_cols and "index" not in present_cols:
        r["sentence_index"] = r.pop("index")

    # start_char/end_char -> start_offset/end_offset (if DB uses offsets)
    if "start_char" in r and "start_offset" in present_cols and "start_char" not in present_cols:
        r["start_offset"] = r.pop("start_char")
    if "end_char" in r and "end_offset" in present_cols and "end_char" not in present_cols:
        r["end_offset"] = r.pop("end_char")

    # Ensure required basics exist if present in schema
    for key in ("id", "transcript_id", "text"):
        if key in present_cols and key not in r:
            r[key] = None

    # Finally, drop any keys not in the table to avoid unknown-column errors
    r = {k: v for k, v in r.items() if k in present_cols}
    return r

def _quote_ident(name: str) -> str:
    # Basic identifier quoting for SQLite/SQL: "identifier"
    # NOTE: we assume 'name' comes from our own code/PRAGMA, not direct user input.
    return f'"{name}"'

def _upsert_many(table: str, rows: List[Dict[str, Any]]) -> int:
    """
    SQLite-friendly bulk insert using INSERT OR IGNORE, with:
      - quoted identifiers (handles reserved words like "index"),
      - schema-aware column mapping per row.
    """
    if not rows:
        return 0

    with engine.begin() as conn:
        conn.execute(sql("PRAGMA foreign_keys=ON"))
        present = _table_columns(conn, table)

        # Map each row to the live schema
        mapped: List[Dict[str, Any]] = []
        for row in rows:
            mapped_row = (
                _map_segment_row_to_schema(row, present)
                if table == "segments" else
                {k: v for k, v in row.items() if k in present}  # pass-through for other tables
            )
            if mapped_row:
                mapped.append(mapped_row)

        if not mapped:
            return 0

        # Build a stable column list across all rows (union, but stable order)
        cols = []
        seen = set()
        for r in mapped:
            for c in r.keys():
                if c not in seen:
                    seen.add(c)
                    cols.append(c)

        # Quoted column list and named placeholders
        collist = ", ".join(_quote_ident(c) for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)

        stmt = f'INSERT OR IGNORE INTO {_quote_ident(table)} ({collist}) VALUES ({placeholders})'
        params = [{c: r.get(c) for c in cols} for r in mapped]

        conn.execute(sql(stmt), params)
        conn.commit()
        return len(mapped)


@router.post("/docx")
async def import_docx(transcript_id: str = Form(...), file: UploadFile = File(...)):
    # Save to temp
    tmp_dir = os.path.join("/tmp", "qualiagent")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.docx")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        parsed = parse_docx(path=Path(tmp_path), transcript_id=transcript_id)
    except Exception as e:
        raise HTTPException(400, f"Parse error: {e}")
    finally:
        try: os.remove(tmp_path)
        except: pass

    # Upsert to DB
    segs = parsed.get("segments", [])
    evs  = parsed.get("events", [])
    cbs  = parsed.get("codebook", [])
    labs = parsed.get("labels", [])
    n1 = _upsert_many("segments", segs)
    n2 = _upsert_many("events", evs)
    n3 = _upsert_many("codebook", cbs)
    n4 = _upsert_many("event_labels", labs)

    with engine.begin() as conn:
    # Upsert transcript row
        conn.execute(sql("""
        INSERT OR IGNORE INTO transcripts(id, title, notes) VALUES(:id, :title, :notes)
        """), {"id": transcript_id, "title": transcript_id, "notes": None})

        # Recompute stats
        conn.execute(sql("""
        INSERT INTO transcript_stats(transcript_id, n_segments, n_events, n_proposed, n_accepted, updated_at)
        SELECT :tid,
                (SELECT COUNT(*) FROM segments WHERE transcript_id=:tid),
                (SELECT COUNT(*) FROM events WHERE transcript_id=:tid),
                (SELECT COUNT(*) FROM events WHERE transcript_id=:tid AND status='proposed'),
                (SELECT COUNT(*) FROM events WHERE transcript_id=:tid AND status='accepted'),
                CURRENT_TIMESTAMP
        ON CONFLICT(transcript_id) DO UPDATE SET
            n_segments=excluded.n_segments,
            n_events=excluded.n_events,
            n_proposed=excluded.n_proposed,
            n_accepted=excluded.n_accepted,
            updated_at=CURRENT_TIMESTAMP
        """), {"tid": transcript_id})
        conn.commit()

        return {"ok": True, "counts": {"segments": n1, "events": n2, "codebook": n3, "event_labels": n4}}
