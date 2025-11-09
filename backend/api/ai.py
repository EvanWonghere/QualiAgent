# backend/api/ai.py
from __future__ import annotations
import os, json, hashlib
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text as sql
from backend.db import SessionLocal
from dotenv import load_dotenv

load_dotenv()  # load .env if present
router = APIRouter()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class SuggestIn(BaseModel):
    text: Optional[str] = None
    transcript_id: Optional[str] = None
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    top_k: int = 5

class SuggestOut(BaseModel):
    summary: str
    candidate_codes: List[Dict[str, Any]]
    novelty: Optional[Dict[str, Any]] = None   # { name, rationale } if proposed

def _prompt_hash(p: str) -> str:
    return hashlib.sha256(p.encode("utf-8")).hexdigest()[:16]

def _load_context(db: Session, body: SuggestIn):
    if body.text:
        text = body.text
    elif body.transcript_id:
        q = "SELECT text FROM segments WHERE transcript_id=:tid"
        params = {"tid": body.transcript_id}
        if body.start_index is not None and body.end_index is not None:
            q += " AND [index] BETWEEN :s AND :e"
            params["s"] = body.start_index; params["e"] = body.end_index
        rows = db.execute(sql(q), params).mappings().all()
        text = "\n".join([r["text"] for r in rows])
    else:
        raise HTTPException(400, "Provide `text` or (`transcript_id` and indices).")
    cb = db.execute(sql("SELECT id,name,definition FROM codebook WHERE status!='deprecated'")).mappings().all()
    return text, [dict(r) for r in cb]

@router.post("/suggest_codes", response_model=List[SuggestOut])
def suggest_codes(body: SuggestIn, db: Session = Depends(get_db)):
    text, codebook = _load_context(db, body)
    if not text.strip():
        raise HTTPException(400, "Empty text.")

    # OpenAI on?
    use_llm = bool(os.getenv("OPENAI_API_KEY")) and os.getenv("USE_LLM","1") not in ("0","false","")
    outputs: List[SuggestOut] = []

    if use_llm:
        try:
            from openai import OpenAI
            base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE_URL")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url) if base_url else OpenAI()
            model = os.getenv("OPENAI_LLM_MODEL","gpt-4o-mini")

            # Few-shot instruction
            cb_lines = "\n".join([f"- {c['name']}: {c.get('definition','')}" for c in codebook]) or "(empty codebook)"
            sys = (
                "You are a qualitative coding assistant. Given text and a codebook,"
                " extract concise event summaries (<=40 chars each) and suggest up to 3 codes per event,"
                " prioritizing existing codes. If none fit, propose ONE new code name with rationale."
                " Return strict JSON list where each item has keys: summary, candidate_codes, novelty."
                " candidate_codes is a list of {code_name, codebook_id|null, confidence}."
                " novelty is null or {name, rationale}."
            )
            user = f"Codebook:\n{cb_lines}\n\nText:\n{text[:8000]}"
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":sys},{"role":"user","content":user}],
                temperature=0.1
            )
            content = resp.choices[0].message.content or "[]"
            # ✅ --- 关键修复：清理AI返回的Markdown代码块 ---
            cleaned_content = content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:] # 移除 ```json
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3] # 移除 ```
            cleaned_content = cleaned_content.strip() # 再次清理空白
            # --- 修复结束 ---

            # 检查清理后的 content
            if not cleaned_content or not cleaned_content.startswith(("{", "[")):
                raise ValueError(f"AI returned non-JSON or empty content. Raw response: '{content}'")
            
            data = json.loads(cleaned_content)
            # map code_name -> codebook_id if exact match
            name_to_id = {c["name"]: c["id"] for c in codebook}
            for it in data:
                for cc in it.get("candidate_codes", []):
                    n = (cc.get("code_name") or "").strip()
                    cc["codebook_id"] = cc.get("codebook_id") or name_to_id.get(n)
                outputs.append(SuggestOut(**it))
            # audit
            ph = _prompt_hash(cb_lines)
            db.execute(sql(
                "INSERT INTO ai_calls(id, endpoint, model, params_json, prompt_hash, related_event_id) "
                "VALUES(:id,'/ai/suggest_codes',:m,:p,:h,NULL)"
            ), {"id": f"ai.suggest.{ph}", "m": model, "p": json.dumps({'len_text':len(text)}), "h": ph})
            return outputs
        except Exception as e:
            # 打印详细错误到您的后端终端
            print(f"CRITICAL ERROR in /ai/suggest_codes: {e}")
            import traceback
            traceback.print_exc() # 打印完整的堆栈跟踪

            # 将错误信息返回给前端，而不是回退到
            raise HTTPException(
                status_code=500, 
                detail=f"AI call failed: {e}"
            )

    # Heuristic fallback: character bigram overlap between sentence-level chunks and code names
    def _chunks(t: str) -> List[str]:
        import re
        parts = re.split(r"[。！？!?]\s*", t)
        return [p.strip() for p in parts if p.strip()]

    def _ngrams(s: str, n=2) -> set:
        s = "".join(str(s).split())
        return set(s[i:i+n] for i in range(max(len(s)-n+1, 1)))

    chs = _chunks(text)
    for c in chs[:10]:
        scores = []
        cg = _ngrams(c, 2)
        for code in codebook:
            g = _ngrams(code["name"], 2)
            j = len(cg & g) / max(len(cg | g), 1)
            scores.append((j, code))
        scores.sort(key=lambda x: x[0], reverse=True)
        top = [{"code_name": sc[1]["name"], "codebook_id": sc[1]["id"], "confidence": round(sc[0], 3)} for sc in scores[:3]]
        novelty = None
        if top and top[0]["confidence"] < 0.05:  # very low similarity → novelty
            novelty = {"name": f"新主题-{c[:6]}", "rationale": "低相似度，建议新类目"}
        outputs.append(SuggestOut(summary=c[:40], candidate_codes=top, novelty=novelty))
    return outputs
