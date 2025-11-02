# backend/repositories/sql_repo.py
from typing import List, Optional, Dict, Any
from sqlalchemy import text as sql
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

def list_codebook(db: Session, include_deprecated: bool = False) -> List[Dict[str, Any]]:
    q_dep = "SELECT * FROM codebook ORDER BY name"
    q_act = "SELECT * FROM codebook WHERE status != 'deprecated' ORDER BY name"
    q = q_dep if include_deprecated else q_act
    
    try: # ✨ Add try block
        return [dict(r) for r in db.execute(sql(q)).mappings().all()]
    except OperationalError: # ✨ Catch error if table doesn't exist
        return [] # Return an empty list instead of crashing

def list_segments(db: Session, transcript_id: str) -> List[Dict[str, Any]]:
    q = ("SELECT id, transcript_id, [index], speaker, text "
         "FROM segments WHERE transcript_id=:tid ORDER BY [index]")
    try: # ✨ Add try block
        return [dict(r) for r in db.execute(sql(q), {"tid": transcript_id}).mappings().all()]
    except OperationalError:
        return []

def list_review_queue(db: Session, transcript_id: Optional[str] = None) -> List[Dict[str, Any]]:
    base = ("SELECT e.*, "
            "(SELECT json_group_array(json_object('id', el.id,'event_id', el.event_id,'codebook_id', el.codebook_id,'created_by', el.created_by,'created_at', el.created_at,'rationale', el.rationale)) "
            " FROM event_labels el WHERE el.event_id = e.id) AS labels_json "
            "FROM events e WHERE e.status='proposed' AND e.created_by='AI'")
    
    try: # ✨ Add try block
        if transcript_id:
            base += " AND e.transcript_id=:tid"
            rows = db.execute(sql(base), {"tid": transcript_id}).mappings().all()
        else:
            rows = db.execute(sql(base)).mappings().all()
    except OperationalError:
        rows = [] # If query fails, just use an empty list

    out = []
    import json
    for r in rows:
        labels = json.loads(r["labels_json"] or "[]")
        e = dict(r)
        e.pop("labels_json", None)
        out.append({"event": e, "labels": labels})
    return out

def get_event(db: Session, event_id: str) -> Optional[Dict[str, Any]]:
    try: # ✨ Add try block
        r = db.execute(sql("SELECT * FROM events WHERE id=:id"), {"id": event_id}).mappings().first()
        return dict(r) if r else None
    except OperationalError:
        return None

def update_event_status(db: Session, event_id: str, status: str) -> int:
    return db.execute(sql("UPDATE events SET status=:s WHERE id=:id"), {"s": status, "id": event_id}).rowcount

def patch_event(db: Session, event_id: str, fields: Dict[str, Any]) -> int:
    if not fields:
        return 0
    sets = ", ".join([f"{k}=:{k}" for k in fields.keys()])
    fields["id"] = event_id
    return db.execute(sql(f"UPDATE events SET {sets} WHERE id=:id"), fields).rowcount

def insert_label_review(db: Session, label_id: str, reviewer: str, decision: str, notes: Optional[str]):
    db.execute(sql(
        "INSERT INTO label_reviews(id,event_label_id,reviewer,decision,notes,created_at) "
        "VALUES(:id,:lid,:r,:d,:n,CURRENT_TIMESTAMP)"
    ), {"id": f"r.{label_id}", "lid": label_id, "r": reviewer, "d": decision, "n": notes})

def add_event_label(db: Session, event_id: str, codebook_id: str, created_by: str, rationale: Optional[str]):
    db.execute(sql(
        "INSERT OR IGNORE INTO event_labels(id,event_id,codebook_id,created_by,rationale,created_at) "
        "VALUES(:id,:e,:c,:by,:ra,CURRENT_TIMESTAMP)"
    ), {"id": f"l.{event_id}.{codebook_id}", "e": event_id, "c": codebook_id, "by": created_by, "ra": rationale})

def merge_codebook(db: Session, from_id: str, into_id: str):
    db.execute(sql("UPDATE event_labels SET codebook_id=:into WHERE codebook_id=:frm"), {"into": into_id, "frm": from_id})
    db.execute(sql("UPDATE codebook SET status='deprecated' WHERE id=:frm"), {"frm": from_id})
