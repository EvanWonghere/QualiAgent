# backend/api/events_v2.py
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text as sql
from datetime import datetime, timezone
from dotenv import load_dotenv
import os, hashlib
from backend.db import SessionLocal

load_dotenv()
router = APIRouter()

def get_db():
    db = SessionLocal(); 
    try: yield db
    finally: db.close()

def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

def _list_unlabeled_segments(db: Session, transcript_id: str):
    # (此函数不变)
    q = """
    SELECT s.id, s.text
    FROM segments s
    LEFT JOIN events e ON e.segment_id = s.id AND e.status IN ('accepted','proposed')
    WHERE s.transcript_id=:tid AND e.id IS NULL
    ORDER BY s.[index] ASC
    LIMIT 200
    """
    return [dict(r) for r in db.execute(sql(q), {"tid": transcript_id}).mappings().all()]

def _list_codebook(db: Session):
    # (此函数不变)
    rows = db.execute(sql("SELECT id,name,definition FROM codebook WHERE status!='deprecated'")).mappings().all()
    return [dict(r) for r in rows]

@router.post("/propose_missing/{transcript_id}")
def propose_missing(transcript_id: str, db: Session = Depends(get_db)):
    segs = _list_unlabeled_segments(db, transcript_id)
    if not segs:
        return {"created": 0, "events": []}

    cb = _list_codebook(db)
    cb_text = "\n".join([f"- {c['name']}: {c.get('definition','')}" for c in cb]) or "(no codebook yet)"

    use_openai = os.getenv("OPENAI_API_KEY") and os.getenv("USE_EMBEDDINGS","1") not in ("0","false","")
    created = 0
    out = []
    
    if use_openai:
        try:
            # ... (OpenAI client setup 不变) ...
            from openai import OpenAI
            base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE_URL")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url) if base_url else OpenAI()
            model = os.getenv("OPENAI_LLM_MODEL","gpt-4o-mini")
            
            for s in segs:
                # ... (AI prompt and call 不变) ...
                sys_prompt = "Extract one concise event summary (<= 30 chars). If no event, return 'NONE'. Then choose best matching code name from the list if any."
                user = f"Codes:\n{cb_text}\n\nText:\n{s['text']}\n\nReturn JSON with keys: summary, code_name"
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":sys_prompt},{"role":"user","content":user}],
                    temperature=0.1
                )
                content = resp.choices[0].message.content or "{}"
                import json
                js = {}
                try: js = json.loads(content)
                except: js = {"summary": content.strip()[:30], "code_name": None}
                summary = (js.get("summary") or "").strip()[:60]
                code_name = (js.get("code_name") or "").strip()
                if not summary or summary.upper() == "NONE":
                    continue
                
                eid = f"e.{s['id']}"
                
                # ✅ --- 关键修复 (1/3) ---
                # 将 INSERT OR IGNORE 改为 INSERT OR REPLACE
                # 这将删除任何已存在的 (比如 'rejected') event，并插入新的 'proposed' event
                db.execute(sql(
                    "INSERT OR REPLACE INTO events(id,transcript_id,segment_id,start_char,end_char,summary,created_by,status,confidence,created_at,event_kind,raw_excerpt) "
                    "VALUES(:id,:tid,:sid,NULL,NULL,:sum,'AI','proposed',NULL,CURRENT_TIMESTAMP,:kind,:raw)"
                ), {"id": eid, "tid": transcript_id, "sid": s["id"], "sum": summary, "kind": code_name or None, "raw": s["text"][:200]})
                
                created += 1
                out.append({"id": eid, "summary": summary, "code_name": code_name})
                
                if code_name:
                    row = db.execute(sql("SELECT id FROM codebook WHERE name=:n"), {"n": code_name}).mappings().first()
                    if row:
                        # ✅ --- 关键修复 (2/3) ---
                        # 同样使用 INSERT OR REPLACE 来确保 label 被更新
                        db.execute(sql(
                            "INSERT OR REPLACE INTO event_labels(id,event_id,codebook_id,created_by,created_at) "
                            "VALUES(:id,:e,:c,'AI',CURRENT_TIMESTAMP)"
                        ), {"id": f"l.{eid}.{row['id']}", "e": eid, "c": row["id"]})
            
            phash = _prompt_hash(cb_text)
            # ✅ --- 关键修复 (3/3) ---
            # 同样使用 INSERT OR REPLACE 来更新 ai_calls
            db.execute(sql(
                "INSERT OR REPLACE INTO ai_calls(id, endpoint, model, params_json, prompt_hash, related_event_id) "
                "VALUES(:id, :ep, :m, :p, :h, NULL)"
            ), {"id": f"ai.{transcript_id}.{phash}", "ep": "/events/propose_missing", "m": model, "p": "{}", "h": phash})
            
            db.commit() # ✨ 确保事务被提交
            return {"created": created, "events": out}
        
        except Exception as e:
            db.rollback() # ✨ 出错时回滚
            pass

    # Fallback mock:
    for s in segs:
        eid = f"e.{s['id']}"
        # ✅ --- 关键修复 (Mock) ---
        # Mock 逻辑同样需要使用 INSERT OR REPLACE
        db.execute(sql(
            "INSERT OR REPLACE INTO events(id,transcript_id,segment_id,start_char,end_char,summary,created_by,status,confidence,created_at,event_kind,raw_excerpt) "
            "VALUES(:id,:tid,:sid,NULL,NULL,:sum,'AI','proposed',0.5,CURRENT_TIMESTAMP,NULL,:raw)"
        ), {"id": eid, "tid": transcript_id, "sid": s["id"], "sum": s["text"][:30], "raw": s["text"][:200]})
        out.append({"id": eid, "summary": s["text"][:30], "code_name": None})
        created += 1
    
    db.commit() # ✨ 确保事务被提交
    return {"created": created, "events": out}