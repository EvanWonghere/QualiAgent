# backend/importers/db_writer.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Dict, Any, List
from sqlalchemy import text as sql
from backend.db import engine

def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def _upsert_many(table: str, rows: List[Dict[str, Any]], unique_cols: List[str] | None = None) -> int:
    """
    Simple SQLite-friendly upsert using INSERT OR IGNORE.
    Assumes incoming rows include the primary key field when appropriate.
    """
    if not rows:
        return 0
    cols = sorted({k for r in rows for k in r.keys()})
    placeholders = ", ".join(":"+c for c in cols)
    collist = ", ".join(f'"{c}"' for c in cols)
    stmt = f'INSERT OR IGNORE INTO "{table}" ({collist}) VALUES ({placeholders})'
    params = [{c: r.get(c) for c in cols} for r in rows]

    try:
        with engine.begin() as conn:
            conn.execute(sql("PRAGMA foreign_keys=ON"))
            conn.execute(sql(stmt), params)
        return len(rows)
    except Exception as e:
        print(f"Error executing upsert for table '{table}': {e}")
        print(f"SQL: {stmt}")
        raise

def _map_codebook_ids_to_existing(cbs: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Return map incoming_codebook_id -> db_codebook_id based on UNIQUE(name).
    If a name already exists in DB with a different id, map to the DB id.
    Otherwise, map to the incoming id (row we just inserted/ignored).
    """
    id2name = {cb.get('id'): cb.get('name') for cb in cbs if cb.get('id') and cb.get('name')}
    if not id2name:
        return {}
    incoming_ids = list(id2name.keys())
    name_set = list(set(id2name.values()))
    result: Dict[str, str] = {}

    with engine.begin() as conn:
        conn.execute(sql("PRAGMA foreign_keys=ON"))
        # Fetch ids by name that already exist in DB
        for name in name_set:
            row = conn.execute(sql('SELECT id FROM codebook WHERE name = :name'), {'name': name}).fetchone()
            if row:
                db_id = row[0]
                for in_id, nm in id2name.items():
                    if nm == name:
                        result[in_id] = db_id
        # For any remaining incoming ids, verify they exist by id and map to themselves
        for in_id in incoming_ids:
            if in_id in result:
                continue
            row = conn.execute(sql('SELECT id FROM codebook WHERE id = :id'), {'id': in_id}).fetchone()
            if row:
                result[in_id] = in_id
    return result

def write_imported_dir(dir_path: str | Path) -> Dict[str, int]:
    """
    Reads JSONL files from an importer output directory and upserts into V2 tables.
    Supported: *.segments.jsonl, *.events.jsonl, *.codebook.jsonl, *.labels.jsonl
    """
    p = Path(dir_path)
    segs: List[Dict[str, Any]] = []
    evs: List[Dict[str, Any]] = []
    cbs: List[Dict[str, Any]] = []
    labs: List[Dict[str, Any]] = []
    counts = {"segments": 0, "events": 0, "codebook": 0, "event_labels": 0}

    # Load files
    for fp in sorted(p.glob("*.segments.jsonl")):
        segs.extend(list(_iter_jsonl(fp)))
    for fp in sorted(p.glob("*.events.jsonl")):
        evs.extend(list(_iter_jsonl(fp)))
    for fp in sorted(p.glob("*.codebook.jsonl")):
        for data in _iter_jsonl(fp):
            if isinstance(data, dict):
                cbs.append(data)
    for fp in sorted(p.glob("*.labels.jsonl")):
        labs.extend(list(_iter_jsonl(fp)))

    # Upserts
    if segs: counts["segments"] += _upsert_many("segments", segs)
    if evs: counts["events"] += _upsert_many("events", evs)
    if cbs:
        counts["codebook"] += _upsert_many("codebook", cbs)
        # Normalize label.codebook_id to the real DB id for that name
        if labs:
            id_map = _map_codebook_ids_to_existing(cbs)
            if id_map:
                for l in labs:
                    cbid = l.get('codebook_id')
                    if cbid and cbid in id_map:
                        l['codebook_id'] = id_map[cbid]

    if labs: counts["event_labels"] += _upsert_many("event_labels", labs)

    return counts
