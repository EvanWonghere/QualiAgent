# backend/api/irr.py
from __future__ import annotations
import uuid, random
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text as sql
from sqlalchemy.orm import Session
from backend.db import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ---------- Models ----------
class TaskCreateIn(BaseModel):
    name: str
    item_type: str = Field(pattern="^(event|segment)$")
    scope_transcript_id: Optional[str] = None
    source: str = "proposed"   # for events: 'proposed'|'accepted'; for segments: 'all'
    sample_size: int = 20

class JudgmentIn(BaseModel):
    item_id: str
    decision: Optional[str] = None       # 'accept' | 'reject' (for events)
    codebook_id: Optional[str] = None    # single-label nominal

class SubmitIn(BaseModel):
    coder_id: str
    judgments: List[JudgmentIn]

# ---------- Helpers ----------
def _uuid(prefix="irr"):
    return f"{prefix}.{uuid.uuid4().hex[:12]}"

# ---------- Endpoints ----------
@router.post("/tasks")
def create_task(body: TaskCreateIn, db: Session = Depends(get_db)):
    tid = _uuid("task")
    db.execute(sql(
        "INSERT INTO irr_tasks(id,name,item_type,scope_transcript_id,source,sample_size) VALUES(:i,:n,:t,:s,:src,:k)"
    ), {"i": tid, "n": body.name, "t": body.item_type, "s": body.scope_transcript_id, "src": body.source, "k": body.sample_size})

    # Sample items
    if body.item_type == "event":
        base = "SELECT id FROM events WHERE status=:st"
        params = {"st": body.source if body.source in ("proposed","accepted") else "proposed"}
        if body.scope_transcript_id:
            base += " AND transcript_id=:tid"; params["tid"] = body.scope_transcript_id
    else:
        base = "SELECT id FROM segments"
        params = {}
        if body.scope_transcript_id:
            base += " WHERE transcript_id=:tid"; params["tid"] = body.scope_transcript_id
    base += " ORDER BY RANDOM() LIMIT :k"; params["k"] = body.sample_size
    rows = db.execute(sql(base), params).mappings().all()
    for r in rows:
        db.execute(sql(
            "INSERT INTO irr_items(id,task_id,item_type,item_id) VALUES(:i,:t,:ty,:it)"
        ), {"i": _uuid("item"), "t": tid, "ty": body.item_type, "it": r["id"]})

    db.commit()
    return {"ok": True, "task_id": tid, "count": len(rows)}

@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    t = db.execute(sql("SELECT * FROM irr_tasks WHERE id=:id"), {"id": task_id}).mappings().first()
    if not t: raise HTTPException(404, "task not found")
    items = db.execute(sql("SELECT * FROM irr_items WHERE task_id=:t"), {"t": task_id}).mappings().all()
    return {"task": dict(t), "items": [dict(i) for i in items]}

@router.post("/tasks/{task_id}/judge")
def submit_judgments(task_id: str, body: SubmitIn, db: Session = Depends(get_db)):
    exists = db.execute(sql("SELECT 1 FROM irr_tasks WHERE id=:id"), {"id": task_id}).first()
    if not exists: raise HTTPException(404, "task not found")
    for j in body.judgments:
        db.execute(sql(
            "INSERT OR REPLACE INTO irr_judgments(id,task_id,item_id,coder_id,decision,codebook_id) "
            "VALUES(:id,:t,:it,:c,:d,:cb)"
        ), {"id": f"j.{task_id}.{body.coder_id}.{j.item_id}", "t": task_id, "it": j.item_id,
            "c": body.coder_id, "d": j.decision, "cb": j.codebook_id})
    
    db.commit()
    return {"ok": True, "count": len(body.judgments)}

@router.get("/tasks/{task_id}/metrics")
def irr_metrics(task_id: str, db: Session = Depends(get_db)):
    # Pull judgments per item per coder
    rows = db.execute(sql(
        "SELECT item_id, coder_id, decision, codebook_id FROM irr_judgments WHERE task_id=:t"
    ), {"t": task_id}).mappings().all()
    if not rows: return {"items": 0, "coders": 0, "percent_agreement": None, "kappa": None}

    # Group per item: {item_id: {coder_id: (decision, codebook_id)}}
    per_item: Dict[str, Dict[str, Dict[str, Any]]] = {}
    coders = set()
    for r in rows:
        coders.add(r["coder_id"])
        per_item.setdefault(r["item_id"], {})[r["coder_id"]] = {"decision": r["decision"], "codebook_id": r["codebook_id"]}

    # Only items with exactly two coders contribute to agreement in this v1
    items = [v for v in per_item.values() if len(v) >= 2]
    if not items: return {"items": 0, "coders": len(coders), "percent_agreement": None, "kappa": None}

    # Compute agreement on decision if present; else on codebook_id
    agree, total = 0, 0
    # Build confusion for Cohen's kappa (binary accept/reject OR nominal label)
    # We’ll implement binary kappa if decisions are present for most items; else nominal on codebook_id (exact match).
    decisions_mode = sum(1 for v in items if all(d.get("decision") for d in v.values())) >= len(items) * 0.7

    if decisions_mode:
        # Map accept/reject to 1/0
        def norm(x): return 1 if (x or "").lower() == "accept" else 0
        a_counts = [0, 0]  # coder A
        b_counts = [0, 0]  # coder B
        agree_n = 0
        for it in items:
            (c1, c2) = list(it.keys())[:2]
            d1 = norm(it[c1]["decision"]); d2 = norm(it[c2]["decision"])
            a_counts[d1] += 1; b_counts[d2] += 1
            agree_n += 1 if d1 == d2 else 0
        total = len(items)
        po = agree_n / total
        pa = a_counts[1] / total; pb = b_counts[1] / total  # prevalence of "accept"
        pe = pa*pb + (1-pa)*(1-pb)
        kappa = (po - pe) / (1 - pe + 1e-9)
        return {"items": total, "coders": len(coders), "target": "decision", "percent_agreement": po, "kappa": kappa}
    else:
        # Nominal agreement on single codebook_id (exact match)
        agree_n = 0
        total = 0
        for it in items:
            (c1, c2) = list(it.keys())[:2]
            l1 = it[c1]["codebook_id"]; l2 = it[c2]["codebook_id"]
            if l1 is None or l2 is None: continue
            total += 1
            agree_n += 1 if l1 == l2 else 0
        po = (agree_n / total) if total else None
        # For nominal κ we’d need full confusion; for now we report percent only
        return {"items": total, "coders": len(coders), "target": "codebook_id", "percent_agreement": po, "kappa": None}
